"""Run the SDK's full EDRAM dump and usage methods at controlled GPU boundaries.

Project work: djultra64. Native execution belongs exclusively on Windows.
The omitted resolve consumer represents an aborted caller, not a model of Resolve.
"""
from pipeline_completion_fixture import extract


def generate(sdk):
    source = (sdk / 'src/graphics/vulkan/render_target_cache.cpp').read_text()
    signatures = (
        'void VulkanRenderTargetCache::GetEdramBufferUsageMasks(',
        'void VulkanRenderTargetCache::UseEdramBuffer(',
        'void VulkanRenderTargetCache::MarkEdramBufferModified(',
        'void VulkanRenderTargetCache::CommitEdramBufferShaderWrites(',
        'bool VulkanRenderTargetCache::DumpRenderTargets(',
    )
    notice = source[:source.index('#include')]
    return notice + PREFIX + '\n'.join(extract(source, s) for s in signatures) + MAIN


PREFIX = r'''
#include <vulkan/vulkan.h>
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <iostream>
#include <string>
#include <vector>
#define assert_true(x) assert(x)
#define assert_unhandled_case(x) assert(false)
#define assert_always(x) assert(false)
namespace xenos {constexpr uint32_t kEdramTileWidthSamples=80,kEdramTileHeightSamples=16;}
struct Event {bool dispatch;VkPipelineStageFlags src=0,dst=0;VkAccessFlags read=0,write=0;};
struct Observed {inline static std::vector<Event> events;};
struct DeferredCommandBuffer {
 void CmdVkBindDescriptorSets(VkPipelineBindPoint,VkPipelineLayout,uint32_t,uint32_t,const VkDescriptorSet*,uint32_t,const uint32_t*){}
 void CmdVkPushConstants(VkPipelineLayout,VkShaderStageFlags,uint32_t,uint32_t,const void*){}
 void CmdVkDispatch(uint32_t x,uint32_t y,uint32_t z){assert(x&&y&&z==1);Observed::events.push_back({true});}
};
struct Processor {
 DeferredCommandBuffer commands;
 std::vector<Event> pending;
 DeferredCommandBuffer& deferred_command_buffer(){return commands;}
 bool PushBufferMemoryBarrier(VkBuffer buffer,VkDeviceSize offset,VkDeviceSize size,VkPipelineStageFlags src,VkPipelineStageFlags dst,VkAccessFlags read,VkAccessFlags write,uint32_t=VK_QUEUE_FAMILY_IGNORED,uint32_t=VK_QUEUE_FAMILY_IGNORED,bool skip_if_equal=true){
  assert(buffer==(VkBuffer)1&&offset==0&&size==VK_WHOLE_SIZE);
  if(skip_if_equal&&src==dst&&read==write)return false;
  pending.push_back({false,src,dst,read,write});return true;
 }
 void PushImageMemoryBarrier(VkImage,const VkImageSubresourceRange&,VkPipelineStageFlags,VkPipelineStageFlags,VkAccessFlags,VkAccessFlags,VkImageLayout,VkImageLayout){}
 void SubmitBarriers(bool){Observed::events.insert(Observed::events.end(),pending.begin(),pending.end());pending.clear();}
 void BindExternalComputePipeline(VkPipeline){}
};
namespace ui {namespace vulkan {namespace util {
VkImageSubresourceRange InitializeSubresourceRange(VkImageAspectFlags flags){return {flags,0,1,0,1};}
}}}
struct RenderTargetKey {
 uint32_t msaa_samples=0,resource_format=0,base_tiles=0;bool is_depth=false;
 bool Is64bpp() const{return false;}uint32_t GetPitchTiles()const{return 32;}
};
struct RenderTarget {virtual ~RenderTarget()=default;};
struct VulkanRenderTarget : RenderTarget {
 uint32_t sort=0;RenderTargetKey key()const{return {};}
 void SetTemporarySortIndex(uint32_t s){sort=s;}uint32_t temporary_sort_index()const{return sort;}
 VkImage image()const{return (VkImage)2;}VkPipelineStageFlags current_stage_mask()const{return VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT;}
 VkAccessFlags current_access_mask()const{return VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT;}
 VkImageLayout current_layout()const{return VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL;}
 void SetUsage(VkPipelineStageFlags,VkAccessFlags,VkImageLayout){}
 VkDescriptorSet GetDescriptorSetTransferSource()const{return (VkDescriptorSet)3;}
};
struct ResolveCopyDumpRectangle {
 RenderTarget* render_target=nullptr;
 struct Dispatch {uint32_t offset=0,width_tiles=1,height_tiles=1;};
 static constexpr uint32_t kMaxDispatches=1;
 uint32_t GetDispatches(uint32_t,uint32_t,Dispatch* out)const{*out={};return 1;}
};
struct DumpPipelineKey {uint32_t msaa_samples=0,resource_format=0;bool is_depth=false;};
struct DumpInvocation {
 ResolveCopyDumpRectangle rectangle;DumpPipelineKey pipeline_key;
 DumpInvocation(const ResolveCopyDumpRectangle& r,DumpPipelineKey k):rectangle(r),pipeline_key(k){}
 bool operator<(const DumpInvocation&)const{return false;}
};
struct DumpPitches {uint32_t dest_pitch=0,source_pitch=0;bool operator!=(const DumpPitches& b)const{return dest_pitch!=b.dest_pitch||source_pitch!=b.source_pitch;}};
struct DumpOffsets {uint32_t source_base_tiles=0,dispatch_first_tile=0;bool operator!=(const DumpOffsets& b)const{return source_base_tiles!=b.source_base_tiles||dispatch_first_tile!=b.dispatch_first_tile;}};
struct VulkanRenderTargetCache {
 enum class EdramBufferUsage{kFragmentRead,kFragmentReadWrite,kComputeRead,kComputeWrite,kTransferRead,kTransferWrite};
 enum class EdramBufferModificationStatus{kUnmodified,kViaInterlock,kViaUnordered};
 enum class Path{kHostRenderTargets};
 Processor command_processor_;VkBuffer edram_buffer_=(VkBuffer)1;
 EdramBufferUsage edram_buffer_usage_=EdramBufferUsage::kComputeRead;
 EdramBufferModificationStatus edram_buffer_modification_status_=EdramBufferModificationStatus::kUnmodified;
 std::vector<ResolveCopyDumpRectangle> dump_rectangles_;std::vector<DumpInvocation> dump_invocations_;
 VulkanRenderTarget target;unsigned rectangles=1,pipeline_calls=0,fail_pipeline=0,interlock_commits=0;
 VkPipelineLayout dump_pipeline_layout_depth_=(VkPipelineLayout)4,dump_pipeline_layout_color_=(VkPipelineLayout)5;
 VkDescriptorSet edram_storage_buffer_descriptor_set_=(VkDescriptorSet)6;
 static constexpr uint32_t kDumpDescriptorSetEdram=0,kDumpDescriptorSetSource=1,kDumpPushConstantPitches=0,kDumpPushConstantOffsets=1,kDumpSamplesPerGroupX=8,kDumpSamplesPerGroupY=16;
 Path GetPath()const{return Path::kHostRenderTargets;}
 unsigned draw_resolution_scale_x()const{return 1;}unsigned draw_resolution_scale_y()const{return 1;}
 void GetResolveCopyRectanglesToDump(uint32_t,uint32_t,uint32_t,uint32_t,std::vector<ResolveCopyDumpRectangle>& out){out.assign(rectangles,{&target});}
 VkPipeline GetDumpPipeline(DumpPipelineKey){++pipeline_calls;return pipeline_calls==fail_pipeline?VK_NULL_HANDLE:(VkPipeline)7;}
 void PixelShaderInterlockFullEdramBarrierPlaced(){++interlock_commits;}
 static void GetEdramBufferUsageMasks(EdramBufferUsage,VkPipelineStageFlags&,VkAccessFlags&);
 void UseEdramBuffer(EdramBufferUsage);
 void MarkEdramBufferModified(EdramBufferModificationStatus=EdramBufferModificationStatus::kViaUnordered);
 void CommitEdramBufferShaderWrites(EdramBufferModificationStatus=EdramBufferModificationStatus::kViaUnordered);
 bool DumpRenderTargets(uint32_t,uint32_t,uint32_t,uint32_t);
};
'''

MAIN = r'''
int main(int argc,char** argv){
 if(argc!=2)return 2;std::string mode=argv[1];VulkanRenderTargetCache cache;
 auto dump=[&](){return cache.DumpRenderTargets(0,1,1,32);};
 if(mode=="partial_abort"){cache.rectangles=2;cache.fail_pipeline=2;assert(!dump());cache.rectangles=1;cache.fail_pipeline=0;}
 else {assert(dump());}
 if(mode=="normal")cache.UseEdramBuffer(VulkanRenderTargetCache::EdramBufferUsage::kComputeRead);
 if(mode=="empty"){
  cache.rectangles=0;auto n=Observed::events.size(),pending=cache.command_processor_.pending.size();auto commits=cache.interlock_commits;
  assert(dump());return Observed::events.size()==n&&cache.command_processor_.pending.size()==pending&&cache.interlock_commits==commits?0:1;
 }
 if(mode=="fresh")return cache.interlock_commits?1:0;
 auto previous=Observed::events.size();assert(dump());
 bool dependency=false,dispatched=false;
 for(size_t i=previous;i<Observed::events.size();++i){auto e=Observed::events[i];
  if(e.dispatch){dispatched=true;if(!dependency){std::cerr<<"second overlapping dump lacks a prior memory dependency\n";return 1;}}
  else if((e.src&VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT)&&(e.dst&VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT)&&(e.write&VK_ACCESS_SHADER_WRITE_BIT)){
   if(mode=="normal")dependency=(e.read&VK_ACCESS_SHADER_READ_BIT)!=0;
   else dependency=(e.read&VK_ACCESS_SHADER_WRITE_BIT)!=0;
  }
 }
 assert(dispatched);
 if(mode=="normal"&&cache.interlock_commits){std::cerr<<"normal usage transition gained an unnecessary write commit\n";return 1;}
 return 0;
}
'''
