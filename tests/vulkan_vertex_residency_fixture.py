"""Exercise SDK vertex residency and real shared-memory invalidation/range selection.

Project work: djultra64. Native compiler/execution belong on Windows.
The upload boundary copies bytes in RAM instead of submitting GPU commands.
"""
from pipeline_completion_fixture import extract


def generate(sdk):
    cp = (sdk / 'src/graphics/vulkan/command_processor.cpp').read_text()
    shared = (sdk / 'src/graphics/shared_memory.cpp').read_text()
    start = cp.index('  // Ensure vertex buffers are resident.')
    end = cp.index('  // Synchronize the memory pages backing memory scatter', start)
    # Include the actual swap invalidation, before any presenter early return.
    swap = cp.index('void VulkanCommandProcessor::IssueSwap(')
    reset = cp[cp.index('  vertex_buffers_in_sync_[0]', swap):
               cp.index('  if (!graphics_system_)', swap)]
    notice = shared[:shared.index('#include')]
    methods = '\n'.join(extract(shared, signature) for signature in (
        'bool SharedMemory::RequestRanges(',
        'bool SharedMemory::RequestRange(',
        'std::pair<uint32_t, uint32_t> SharedMemory::MemoryInvalidationCallback('))
    invalidate = extract(cp, 'void VulkanCommandProcessor::InvalidateVertexBufferResidency(')
    return (notice + PREFIX + methods + OWNER + invalidate +
            '\nvoid VulkanCommandProcessor::SwapBoundary(){\n' + reset + '}\n' +
            '\nbool VulkanCommandProcessor::Resident(Shader* vertex_shader){\n' +
            'auto& regs=registers;\n' + cp[start:end] + '\nreturn true;\n}\n' + MAIN)


PREFIX = r'''
#include <algorithm>
#include <array>
#include <cassert>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <memory>
#include <mutex>
#include <string>
#include <utility>
#include <vector>
#define SCOPE_profile_cpu_f(...) ((void)0)
#define COUNT_profile_set(...) ((void)0)
#define REXGPU_WARN(...) ((void)0)
#define REXGPU_ERROR(...) ((void)0)
#define REXCVAR_GET(...) false
namespace rex {
template<class T> bool bit_scan_forward(T n,uint32_t* out){
 if(!n)return false;*out=0;while(!(n&T(1))){++*out;n>>=1;}return true;
}
template<class T,size_t N> constexpr size_t countof(const T(&)[N]){return N;}
uint8_t lzcnt(uint64_t n){uint8_t c=0;for(uint64_t b=uint64_t(1)<<63;b && !(n&b);b>>=1)++c;return c;}
uint8_t tzcnt(uint64_t n){uint8_t c=0;for(uint64_t b=1;b && !(n&b);b<<=1)++c;return c;}
}
class SharedMemory {
 public:
 static constexpr uint32_t kBufferSize=uint32_t(1)<<29;
 uint32_t page_size_log2_=12;
 std::array<uint64_t,2048> system_page_flags_valid_{};
 std::array<uint64_t,2048> system_page_flags_valid_and_gpu_written_{};
 std::vector<std::pair<uint32_t,uint32_t>> upload_ranges_;
 struct Region {std::mutex mutex;auto Acquire(){return std::unique_lock<std::mutex>(mutex);}} global_critical_region_;
 std::array<uint8_t,1<<20> cpu{},gpu{};
 unsigned uploads=0;bool allocation_failure=false,upload_failure=false;
 bool RequestRanges(const std::pair<uint32_t,uint32_t>*,size_t);
 bool RequestRange(uint32_t,uint32_t);
 std::pair<uint32_t,uint32_t> MemoryInvalidationCallback(uint32_t,uint32_t,bool);
 bool EnsureHostGpuMemoryAllocated(uint32_t,uint32_t){return !allocation_failure;}
 void FireWatches(uint32_t,uint32_t,bool){}
 bool UploadRanges(const std::vector<std::pair<uint32_t,uint32_t>>& ranges){
  if(upload_failure)return false;
  for(auto [page,count]:ranges){
   assert((page+count)*4096<=cpu.size());
   std::memcpy(gpu.data()+page*4096,cpu.data()+page*4096,count*4096);++uploads;
   for(uint32_t p=page;p<page+count;++p)system_page_flags_valid_[p>>6]|=uint64_t(1)<<(p&63);
  }return true;
 }
 void CpuWrite(uint32_t address,uint8_t value){
  cpu.at(address)=value;MemoryInvalidationCallback(address,1,true);
 }
};
namespace xenos {
enum class FetchConstantType {kVertex,kInvalidVertex,kTexture};
struct xe_gpu_vertex_fetch_t {
 FetchConstantType type=FetchConstantType::kVertex;
 uint32_t address=0,size=4,dword_0=0,dword_1=0;
};
}
struct Shader {
 struct ConstantRegisterMap {uint32_t vertex_fetch_bitmap[3]{};} map;
 const ConstantRegisterMap& constant_register_map()const{return map;}
 void Fetch(unsigned n){map.vertex_fetch_bitmap[n>>5]|=uint32_t(1)<<(n&31);}
};
'''
OWNER = r'''
class VulkanCommandProcessor {
 public:
 struct VertexBufferState {uint32_t address=UINT32_MAX,size=UINT32_MAX;};
 std::array<VertexBufferState,96> vertex_buffer_states_{};
 uint64_t vertex_buffers_in_sync_[2]{};
 struct Registers {
  std::array<xenos::xe_gpu_vertex_fetch_t,96> fetch;
  auto GetVertexFetch(unsigned n)const{return fetch.at(n);}
 } registers;
 SharedMemory memory;SharedMemory* shared_memory_=&memory;
 bool Resident(Shader*);
 void SwapBoundary();
 void InvalidateVertexBufferResidency(uint32_t);
 bool InSync(unsigned n)const{return (vertex_buffers_in_sync_[n>>6]>>(n&63))&1;}
};
'''
MAIN = r'''
bool Check(bool ok,const char* message){if(!ok)std::cerr<<message<<'\n';return ok;}
int main(int argc,char** argv){
 if(argc!=2)return 2;std::string mode=argv[1];auto owner=std::make_unique<VulkanCommandProcessor>();auto& p=*owner;Shader shader;
 unsigned slot=mode=="high_slot"?95:0;shader.Fetch(slot);
 auto& fetch=p.registers.fetch[slot];fetch.address=1024;fetch.size=4;
 p.memory.CpuWrite(4096,11);
 if(!Check(p.Resident(&shader)&&p.memory.gpu[4096]==11&&p.memory.uploads==1,"first draw lost vertex bytes"))return 1;
 if(mode=="first")return 0;
 if(mode=="same_frame")return !Check(p.Resident(&shader)&&p.memory.uploads==1,"same frame recopied valid memory");
 if(mode=="register_invalidation")p.InvalidateVertexBufferResidency(slot);else p.SwapBoundary();
 if(mode=="warm")return !Check(p.Resident(&shader)&&p.memory.gpu[4096]==11&&p.memory.uploads==1,"warm frame recopied valid pages");
 if(mode=="changed_address"){
  fetch.address=2048;p.memory.CpuWrite(8192,23);
  return !Check(p.Resident(&shader)&&p.memory.gpu[8192]==23&&p.memory.uploads==2,"new address lost bytes");
 }
 p.memory.CpuWrite(4096,37);
 if(mode=="changed_size")fetch.size=8;
 if(mode=="allocation_failure")p.memory.allocation_failure=true;
 if(mode=="upload_failure")p.memory.upload_failure=true;
 bool ok=p.Resident(&shader);
 if(mode=="allocation_failure"||mode=="upload_failure"){
  if(!Check(!ok&&!p.InSync(slot)&&p.memory.gpu[4096]==11,"failed residency reported draw ready"))return 1;
  p.memory.allocation_failure=p.memory.upload_failure=false;
  return !Check(p.Resident(&shader)&&p.memory.gpu[4096]==37&&p.InSync(slot),"residency failure could not retry");
 }
 return !Check(ok&&p.memory.gpu[4096]==37&&p.memory.uploads==2&&p.InSync(slot),"rewritten vertex bytes stayed stale");
}
'''
