"""Compile real scratch acquisition, RAII and DMA copy/bind paths at Vulkan boundaries.

Project work: djultra64. Native execution belongs exclusively on Windows.
"""
from pathlib import Path
import re
from pipeline_completion_fixture import extract


def generate(sdk):
    source = (sdk / 'src/graphics/vulkan/command_processor.cpp').read_text()
    header = (sdk / 'include/rex/graphics/vulkan/command_processor.h').read_text()
    acquire = extract(source, 'VulkanCommandProcessor::ScratchBufferAcquisition VulkanCommandProcessor::AcquireScratchGpuBuffer(')
    raii = extract(header, 'class ScratchBufferAcquisition {') + ';'
    increment = re.search(r'static constexpr VkDeviceSize kScratchBufferSizeIncrement\s*=[^;]+;', header).group()
    start = source.index('  ScratchBufferAcquisition guest_dma_index_scratch_buffer;')
    dma = extract(source[start:], 'if (primitive_processing_result.index_buffer_type ==')
    draw_start = source.index('  // Draw.\n', start)
    draw = source[draw_start:source.index('  // Invalidate textures in memexported memory', draw_start)]
    notice = source[:source.index('#if')]
    return notice + PREFIX + raii + increment + OWNER + acquire + RUN_BEGIN + dma + draw + RUN_END + MAIN


PREFIX = r'''
#include <vulkan/vulkan.h>
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <map>
#include <string>
#include <utility>
#include <vector>
#define assert_true(x) assert(x)
#define assert_false(x) assert(!(x))
#define assert_unhandled_case(x) assert(false)
#define REXGPU_ERROR(...) ((void)0)
namespace rex { template<class T> T align(T n,T a){return (n+a-1)/a*a;} }
struct Observed {
  inline static uintptr_t next=256;
  inline static bool fail=false;
  inline static unsigned creates=0,copies=0,binds=0,draws=0,violations=0;
  inline static VkIndexType index_type=VK_INDEX_TYPE_MAX_ENUM;
  inline static VkBuffer copied=nullptr,bound=nullptr;
  inline static VkDeviceSize copy_size=0;
  inline static std::map<VkBuffer,std::pair<VkBufferUsageFlags,VkDeviceSize>> buffers;
  inline static std::vector<VkBuffer> destroyed;
  inline static std::vector<VkDeviceMemory> freed;
  static void Require(bool ok,const char* message){if(!ok){++violations;std::cerr<<message<<'\n';}}
};
namespace ui { namespace vulkan {
struct VulkanDevice {
 struct Functions {
  static void vkDestroyBuffer(VkDevice,VkBuffer b,const VkAllocationCallbacks*){Observed::destroyed.push_back(b);}
  static void vkFreeMemory(VkDevice,VkDeviceMemory m,const VkAllocationCallbacks*){Observed::freed.push_back(m);}
 };
 const Functions& functions() const {static Functions f;return f;}
 VkDevice device() const {return (VkDevice)1;}
};
namespace util {
 enum class MemoryPurpose{kDeviceLocal};
 bool CreateDedicatedAllocationBuffer(const VulkanDevice*,VkDeviceSize size,VkBufferUsageFlags usage,
   MemoryPurpose,VkBuffer& b,VkDeviceMemory& m){
  ++Observed::creates;if(Observed::fail)return false;
  b=(VkBuffer)++Observed::next;m=(VkDeviceMemory)++Observed::next;
  Observed::buffers[b]={usage,size};return true;
 }
}
}}
namespace xenos {enum class IndexFormat{kInt16,kInt32};}
struct PrimitiveProcessor {
 enum class ProcessedIndexBufferType{kNone,kGuestDMA,kHostConverted,kHostBuiltinForAuto,kHostBuiltinForDMA};
 std::pair<VkBuffer,VkDeviceSize> GetConvertedIndexBuffer(uint64_t){return {};}
 std::pair<VkBuffer,VkDeviceSize> GetBuiltinIndexBuffer(uint64_t){return {};}
};
struct VulkanSharedMemory {
 enum class Usage{kRead}; void Use(Usage){}
 VkBuffer buffer() const {return (VkBuffer)0x7000;}
};
struct Commands {
 void CmdVkCopyBuffer(VkBuffer src,VkBuffer dst,uint32_t n,const VkBufferCopy* r){
  assert(src==(VkBuffer)0x7000 && n==1 && r->srcOffset==128 && r->dstOffset==0);
  auto info=Observed::buffers.at(dst);++Observed::copies;Observed::copied=dst;Observed::copy_size=r->size;
  Observed::Require(info.first&VK_BUFFER_USAGE_TRANSFER_DST_BIT,"copy destination missing TRANSFER_DST usage");
  Observed::Require(r->size>0 && r->size<=info.second,"copy outside scratch allocation");
 }
 void CmdVkBindIndexBuffer(VkBuffer b,VkDeviceSize o,VkIndexType t){
  assert(o==0);auto info=Observed::buffers.at(b);++Observed::binds;Observed::bound=b;Observed::index_type=t;
  Observed::Require(info.first&VK_BUFFER_USAGE_INDEX_BUFFER_BIT,"index binding missing INDEX_BUFFER usage");
 }
 void CmdVkDraw(uint32_t,uint32_t,uint32_t,uint32_t){assert(false);}
 void CmdVkDrawIndexed(uint32_t n,uint32_t i,uint32_t f,int32_t v,uint32_t first){
  assert(n && i==1 && !f && !v && !first);++Observed::draws;
 }
};
class VulkanCommandProcessor {
 public:
'''
OWNER = r'''
 bool submission_open_=true,scratch_buffer_used_=false;
 VkBuffer scratch_buffer_=nullptr;VkDeviceMemory scratch_buffer_memory_=nullptr;
 VkDeviceSize scratch_buffer_size_=0;
 VkPipelineStageFlags scratch_buffer_last_stage_mask_=0;
 VkAccessFlags scratch_buffer_last_access_mask_=0;
 uint64_t scratch_buffer_last_usage_submission_=0,submission_current_=10,submission_completed_=9;
 std::vector<std::pair<uint64_t,VkBuffer>> destroy_buffers_;
 std::vector<std::pair<uint64_t,VkDeviceMemory>> destroy_memory_;
 VulkanSharedMemory shared;VulkanSharedMemory* shared_memory_=&shared;
 PrimitiveProcessor primitives;PrimitiveProcessor* primitive_processor_=&primitives;
 Commands deferred_command_buffer_;
 const ui::vulkan::VulkanDevice* GetVulkanDevice() const {static ui::vulkan::VulkanDevice d;return &d;}
 uint64_t GetCurrentSubmission() const {return submission_current_;}
 void PushBufferMemoryBarrier(VkBuffer,VkDeviceSize,VkDeviceSize,VkPipelineStageFlags,VkPipelineStageFlags,VkAccessFlags,VkAccessFlags){}
 void SubmitBarriers(bool){}
 ScratchBufferAcquisition AcquireScratchGpuBuffer(VkDeviceSize,VkPipelineStageFlags,VkAccessFlags);
 bool DrawDma(xenos::IndexFormat,uint32_t);
};
'''
RUN_BEGIN = r'''
bool VulkanCommandProcessor::DrawDma(xenos::IndexFormat format,uint32_t count){
 struct Result {
  PrimitiveProcessor::ProcessedIndexBufferType index_buffer_type=PrimitiveProcessor::ProcessedIndexBufferType::kGuestDMA;
  xenos::IndexFormat host_index_format;
  uint32_t host_draw_vertex_count;
  VkDeviceSize guest_index_base=128;
  uint64_t host_index_buffer_handle=0;
 } primitive_processing_result{PrimitiveProcessor::ProcessedIndexBufferType::kGuestDMA,format,count};
 bool shader_32bit_index_dma=false,memexport_writes_possible=true;
 auto draw_fail=[](const char*){return false;};
 ScratchBufferAcquisition guest_dma_index_scratch_buffer;
'''
RUN_END = r'''
 return true;
}
'''
MAIN = r'''
static bool Check(bool ok,const char* msg){if(!ok)std::cerr<<msg<<'\n';return ok;}
int main(int argc,char** argv){
 if(argc!=2)return 2;std::string mode=argv[1];VulkanCommandProcessor p;
 auto acquire=[&](VkDeviceSize size){return p.AcquireScratchGpuBuffer(size,VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,VK_ACCESS_SHADER_WRITE_BIT);};
 if(mode=="zero") {auto a=acquire(0);return !Check(!a.buffer()&&!Observed::creates&&!p.scratch_buffer_used_,"zero size allocated");}
 if(mode=="failure_empty") {Observed::fail=true;auto a=acquire(32);return !Check(!a.buffer()&&!p.scratch_buffer_&&!p.scratch_buffer_used_,"failed creation changed owner");}
 if(mode=="texture") {auto a=acquire(32);auto flags=Observed::buffers.at(a.buffer()).first;return !Check((flags&(VK_BUFFER_USAGE_TRANSFER_SRC_BIT|VK_BUFFER_USAGE_STORAGE_BUFFER_BIT))==(VK_BUFFER_USAGE_TRANSFER_SRC_BIT|VK_BUFFER_USAGE_STORAGE_BUFFER_BIT),"texture usage lost");}
 VkBuffer old=nullptr;VkDeviceMemory old_memory=nullptr;
 bool reuse=mode.find("reuse")==0,grow=mode.find("grow")==0;
 if(reuse||grow||mode=="failure_grow"||mode=="pending"||mode=="completed") {
  {auto a=acquire(32);old=a.buffer();old_memory=p.scratch_buffer_memory_;}p.submission_current_=11;
 }
 if(mode=="failure_grow"){
  Observed::fail=true;auto a=acquire(VulkanCommandProcessor::kScratchBufferSizeIncrement+4);
  return !Check(!a.buffer()&&p.scratch_buffer_==old&&Observed::destroyed.empty()&&p.destroy_buffers_.empty()&&Observed::freed.empty()&&p.destroy_memory_.empty()&&p.scratch_buffer_memory_==old_memory&&!p.scratch_buffer_used_,"failed grow retired live owner");
 }
 if(mode=="pending"||mode=="completed"){
  if(mode=="completed")p.submission_completed_=10;
  auto a=acquire(VulkanCommandProcessor::kScratchBufferSizeIncrement+4);
  bool retired=mode=="completed" ? Observed::destroyed.size()==1 && Observed::destroyed[0]==old && p.destroy_buffers_.empty() && Observed::freed.size()==1 && Observed::freed[0]==old_memory && p.destroy_memory_.empty()
    : Observed::destroyed.empty() && p.destroy_buffers_.size()==1 && p.destroy_buffers_[0].first==10 && p.destroy_buffers_[0].second==old && Observed::freed.empty() && p.destroy_memory_.size()==1 && p.destroy_memory_[0].first==10 && p.destroy_memory_[0].second==old_memory;
  return !Check(a.buffer()!=old&&retired,"growth retirement changed");
 }
 bool bits32=mode.find("32")!=std::string::npos;
 bool completed=mode.find("completed")!=std::string::npos;
 if(completed)p.submission_completed_=10;
 uint32_t bytes=bits32?4:2;
 uint32_t count=grow?uint32_t(VulkanCommandProcessor::kScratchBufferSizeIncrement/bytes)+1:32;
 bool ok=p.DrawDma(bits32?xenos::IndexFormat::kInt32:xenos::IndexFormat::kInt16,count);
 bool result=Check(ok&&!Observed::violations,"actual DMA copy/bind violates scratch contract")&&
  Check(Observed::copies==1&&Observed::binds==1&&Observed::draws==1,"actual DMA operations not recorded")&&
  Check(Observed::copied==Observed::bound&&Observed::copy_size==VkDeviceSize(count)*bytes,"copy/index snapshot mismatch")&&
  Check(Observed::index_type==(bits32?VK_INDEX_TYPE_UINT32:VK_INDEX_TYPE_UINT16),"index type changed")&&
  Check(Observed::creates==(grow?2u:1u),"unexpected allocation")&&
  Check(!p.scratch_buffer_used_,"RAII ownership not released");
 if(reuse)result=Check(Observed::bound==old,"reuse allocated new scratch")&&result;
 if(grow)result=Check(Observed::bound!=old,"growth reused too-small scratch")&&result;
 return result?0:1;
}
'''
