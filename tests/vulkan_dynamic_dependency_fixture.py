"""Replay real dynamic-entry and deferred methods at the Vulkan command boundary.

Project work: djultra64. Native execution belongs exclusively on Windows.
The spy checks attachment dependencies; it does not execute a GPU or identify
the cause of the captured device loss. SubmitBarriers has no pending work here.
"""
import re
from pipeline_completion_fixture import extract
from vulkan_rendering_attachments_fixture import PREFIX, TARGET


def generate(sdk):
    root = sdk / 'src/graphics/vulkan'
    inc = sdk / 'include/rex/graphics/vulkan'
    cp = (root / 'command_processor.cpp').read_text()
    cache = (root / 'render_target_cache.cpp').read_text()
    header = (inc / 'render_target_cache.h').read_text()
    deferred = (root / 'deferred_command_buffer.cpp').read_text()
    deferred_header = (inc / 'deferred_command_buffer.h').read_text()
    signature = 'void VulkanCommandProcessor::SubmitBarriersAndEnterRenderTargetCacheRenderPass('
    first = cp.index(signature)
    second = cp.index(signature, first + 1)
    entries = extract(cp[first:], signature) + '\n' + extract(cp[second:], signature)
    dependency = (extract(cp, 'static void SynchronizeDynamicRenderingAttachments(')
                  if 'static void SynchronizeDynamicRenderingAttachments(' in cp else '')
    fields = '\n'.join(f'    PFN_{name} {name} = nullptr;' for name in
                       sorted(set(re.findall(r'dfn\.(vk\w+)', deferred))))
    constants = []
    for name in ('kColorDrawLayout', 'kDepthDrawLayout'):
        start = header.index('static constexpr VkImageLayout ' + name)
        constants.append(header[start:header.index(';', start) + 1])
    prefix = PREFIX[:PREFIX.index('class VulkanCommandProcessor {')]
    prefix = prefix.replace('/* API fields */', fields)
    prefix = prefix.replace('static unsigned received_calls = 0;',
                            'static unsigned received_calls = 0;\n' + OBSERVER)
    prefix = prefix.replace('  ++received_calls;', '  ++received_calls;\n  ObserveBegin(info);')
    prefix = prefix.replace('  VulkanDevice() { dfn.vkCmdBeginRendering = Receive; }', '''
  struct Properties {bool dynamicRendering=true;} properties_;
  const Properties& properties()const{return properties_;}
  VulkanDevice() {
    dfn.vkCmdBeginRendering=Receive;dfn.vkCmdEndRendering=ObserveEnd;
    dfn.vkCmdBeginRenderPass=ObserveLegacyBegin;dfn.vkCmdEndRenderPass=ObserveEnd;
    dfn.vkCmdDraw=ObserveDraw;dfn.vkCmdPipelineBarrier=ObserveBarrier;
  }''')
    target = TARGET.replace('/* real layouts */', '\n'.join(constants))
    target = target.replace(' public:\n', ''' public:
  struct Framebuffer {VkExtent2D host_extent{16,16};VkFramebuffer framebuffer=(VkFramebuffer)1;};
''', 1)
    namespace = 'namespace rex::graphics::vulkan {'
    deferred_methods = extract(deferred, namespace)[len(namespace):-1]
    notice = cp[:cp.index('#if')]
    return (notice + '#include <algorithm>\n#include <string>\n#include <utility>\n' + prefix + target
            + extract(cache, 'void VulkanRenderTargetCache::GetLastUpdateRenderingAttachments(')
            + '\nclass VulkanCommandProcessor;\n'
            + extract(deferred_header, 'class DeferredCommandBuffer {') + ';\n'
            + PROCESSOR + deferred_methods + dependency + entries
            + extract(cp, 'void VulkanCommandProcessor::EndRenderPass(') + MAIN)


OBSERVER = r'''
static bool config_dynamic=true,inside=false;
static unsigned begins=0,legacy_begins=0,attachment_barriers=0,violations=0;
static std::vector<std::pair<VkImageView,bool>> active;
static std::vector<std::pair<VkImageView,bool>> dirty;
#define REXCVAR_GET(x) config_dynamic
#define assert_true(x) assert(x)
static bool Check(bool ok,const char* message){if(!ok){++violations;std::cerr<<message<<'\n';}return ok;}
static void ObserveBegin(const VkRenderingInfo* info){
 Check(!inside,"rendering began inside an existing instance");inside=true;++begins;active.clear();
 auto add=[&](const VkRenderingAttachmentInfo* a,bool depth){
  if(!a||!a->imageView)return;
  if(a->loadOp==VK_ATTACHMENT_LOAD_OP_LOAD)
   Check(std::find(dirty.begin(),dirty.end(),std::make_pair(a->imageView,depth))==dirty.end(),"attachment LOAD/WRITE lacks a dependency after the previous instance");
  active.push_back({a->imageView,depth});
 };
 for(uint32_t i=0;i<info->colorAttachmentCount;++i)add(&info->pColorAttachments[i],false);
 add(info->pDepthAttachment,true);
}
static void VKAPI_CALL ObserveEnd(VkCommandBuffer){Check(inside,"end without an active instance");inside=false;}
static void VKAPI_CALL ObserveDraw(VkCommandBuffer,uint32_t,uint32_t,uint32_t,uint32_t){
 Check(inside,"draw outside rendering");for(auto a:active)if(std::find(dirty.begin(),dirty.end(),a)==dirty.end())dirty.push_back(a);
}
static void VKAPI_CALL ObserveLegacyBegin(VkCommandBuffer,const VkRenderPassBeginInfo*,VkSubpassContents){
 Check(!inside,"nested legacy pass");inside=true;++legacy_begins;dirty.clear();
}
static void VKAPI_CALL ObserveBarrier(VkCommandBuffer,VkPipelineStageFlags src,VkPipelineStageFlags dst,VkDependencyFlags flags,uint32_t count,const VkMemoryBarrier* barriers,uint32_t,const VkBufferMemoryBarrier*,uint32_t,const VkImageMemoryBarrier*){
 for(uint32_t i=0;i<count;++i){
  const auto& b=barriers[i];
  Check(b.sType==VK_STRUCTURE_TYPE_MEMORY_BARRIER&&!b.pNext,"invalid dependency structure");
  const bool color=(src&VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT)&&(dst&VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT)&&(b.srcAccessMask&VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT)&&(b.dstAccessMask&VK_ACCESS_COLOR_ATTACHMENT_READ_BIT)&&(b.dstAccessMask&VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT);
  const auto depth_stages=VK_PIPELINE_STAGE_EARLY_FRAGMENT_TESTS_BIT|VK_PIPELINE_STAGE_LATE_FRAGMENT_TESTS_BIT;
  const bool depth=(src&depth_stages)==depth_stages&&(dst&depth_stages)==depth_stages&&(b.srcAccessMask&VK_ACCESS_DEPTH_STENCIL_ATTACHMENT_WRITE_BIT)&&(b.dstAccessMask&VK_ACCESS_DEPTH_STENCIL_ATTACHMENT_READ_BIT)&&(b.dstAccessMask&VK_ACCESS_DEPTH_STENCIL_ATTACHMENT_WRITE_BIT);
  if(color||depth){
   ++attachment_barriers;Check(!inside,"attachment dependency interrupted an existing rendering instance");
   Check(flags&VK_DEPENDENCY_BY_REGION_BIT,"attachment dependency unnecessarily became framebuffer-global");
   dirty.erase(std::remove_if(dirty.begin(),dirty.end(),[&](auto a){return a.second?depth:color;}),dirty.end());
  }
 }
}
'''

PROCESSOR = r'''
class VulkanCommandProcessor {
 public:
  ui::vulkan::VulkanDevice device_;
  VulkanRenderTargetCache cache_;
  VulkanRenderTargetCache* render_target_cache_=&cache_;
  bool submission_open_=true,in_render_pass_=false;
  VkRenderPass current_render_pass_=VK_NULL_HANDLE;
  const VulkanRenderTargetCache::Framebuffer* current_framebuffer_=nullptr;
  DeferredCommandBuffer deferred_command_buffer_;
  VulkanCommandProcessor():deferred_command_buffer_(*this,8){}
  const ui::vulkan::VulkanDevice* GetVulkanDevice()const{return &device_;}
  void SubmitBarriers(bool){} // No pending transition, matching identical usage/layout.
  void SubmitBarriersAndEnterRenderTargetCacheRenderPass(VkRenderPass,const VulkanRenderTargetCache::Framebuffer*);
  void SubmitBarriersAndEnterRenderTargetCacheRenderPass(VkRenderPass,const VulkanRenderTargetCache::Framebuffer*,VkImageView,bool);
  void EndRenderPass();
};
'''

MAIN = r'''
int main(int argc,char** argv){
 if(argc!=2)return 2;std::string mode=argv[1];bool depth=mode.find("depth")!=std::string::npos;
 bool transfer=mode.find("transfer")!=std::string::npos;
 bool same=mode.find("same")!=std::string::npos;
 bool split=mode.find("split")!=std::string::npos;
 bool legacy=mode.find("legacy")!=std::string::npos;config_dynamic=!legacy;
 VulkanCommandProcessor cp;VulkanRenderTarget rt;rt.color=(VkImageView)0x100;rt.depth=(VkImageView)0x200;
 cp.cache_.targets[depth?0:1]=&rt;cp.cache_.last_update_render_pass_key_.depth_and_color_used=depth?1:2;
 if(mode.find("empty")!=std::string::npos){cp.cache_.targets.fill(nullptr);cp.cache_.last_update_render_pass_key_.depth_and_color_used=0;}
 VulkanRenderTargetCache::Framebuffer fb;
 auto enter=[&](){if(transfer)cp.SubmitBarriersAndEnterRenderTargetCacheRenderPass((VkRenderPass)1,&fb,depth?rt.depth:rt.color,depth);else cp.SubmitBarriersAndEnterRenderTargetCacheRenderPass((VkRenderPass)1,&fb);};
 auto draw=[&](){cp.deferred_command_buffer_.CmdVkDraw(3,1,0,0);};
 enter();draw();
 if(!same){
  cp.EndRenderPass();
  // A genuine deferred barrier for an unrelated upload cannot synchronize RT A.
  VkBufferMemoryBarrier unrelated={VK_STRUCTURE_TYPE_BUFFER_MEMORY_BARRIER};
  unrelated.srcAccessMask=VK_ACCESS_SHADER_WRITE_BIT;unrelated.dstAccessMask=VK_ACCESS_TRANSFER_READ_BIT;
  unrelated.srcQueueFamilyIndex=unrelated.dstQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED;unrelated.buffer=(VkBuffer)0x300;unrelated.size=VK_WHOLE_SIZE;
  cp.deferred_command_buffer_.CmdVkPipelineBarrier(VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,VK_PIPELINE_STAGE_TRANSFER_BIT,0,0,nullptr,1,&unrelated,0,nullptr);
  if(split){cp.deferred_command_buffer_.Execute((VkCommandBuffer)1);cp.deferred_command_buffer_.Reset();}
 }
 enter();draw();cp.EndRenderPass();cp.deferred_command_buffer_.Execute((VkCommandBuffer)1);
 if(same)Check(begins==1&&attachment_barriers<=1,"same-instance draws gained a rendering split or extra dependency");
 else if(legacy)Check(!begins&&legacy_begins==2&&!attachment_barriers,"legacy entry changed its synchronization path");
 else Check(begins==2,"reopening no longer records both rendering instances");
 if(mode.find("empty")!=std::string::npos)Check(!attachment_barriers,"attachment-free entry emitted an attachment dependency");
 return violations?1:0;
}
'''
