"""Exercise real queue, compiler publication and drain with a blocking driver seam.
Work: djultra64. Generate C++23 source; no GPU implementation is mocked above creation.
"""
from pathlib import Path
import sys
from pipeline_completion_fixture import extract, PREFIX


def generate(sdk):
    source = (sdk / 'src/graphics/vulkan/pipeline_cache.cpp').read_text()
    signatures = ('void VulkanPipelineCache::QueuePipelineCreation(',
                  'bool VulkanPipelineCache::EnsurePipelineCreated(',
                  'void VulkanPipelineCache::CreationThread(',
                  'void VulkanPipelineCache::CreateQueuedPipelinesOnProcessorThread(',
                  'void VulkanPipelineCache::DrainPipelineCreation(',
                  'void VulkanPipelineCache::GetPipelineAndLayoutByHandle(')
    prefix = PREFIX.replace('struct VulkanPipelineCache {', EXTRA + '\nstruct VulkanPipelineCache {')
    prefix = prefix.replace(' mutable std::atomic<uint64_t>', MEMBERS + '\n mutable std::atomic<uint64_t>', 1)
    return prefix + '\n'.join(extract(source, s) for s in signatures) + TEST

EXTRA = r'''
#include <cassert>
#include <memory>
#include <queue>
#include <utility>
#include <vector>
#define assert_false(x) assert(!(x))
using VkShaderModule = uintptr_t;
struct Event {
 std::mutex lock; std::condition_variable cv; bool signaled = false;
 void Set() { { std::lock_guard guard(lock); signaled = true; } cv.notify_all(); }
 void Reset() { std::lock_guard guard(lock); signaled = false; }
 void Wait() { std::unique_lock guard(lock); cv.wait(guard, [&]{return signaled;}); }
};
namespace rex::thread { void Wait(Event* event, bool) { event->Wait(); } }
'''
MEMBERS = r'''
 struct PipelineCreationArguments {
   std::pair<int,Pipeline>* pipeline;
   const PipelineLayoutProvider* layout;
   bool fail = false;
   std::shared_future<void> gate;
   std::promise<void>* entered = nullptr;
   bool operator<(const PipelineCreationArguments&)const{return false;}
 };
 std::mutex creation_request_lock_;
 std::condition_variable creation_request_cond_;
 std::priority_queue<PipelineCreationArguments> creation_queue_;
 std::vector<int> creation_threads_{1};
 size_t creation_threads_busy_=0,creation_threads_shutdown_from_=SIZE_MAX;
 bool creation_completion_set_event_=false;
 std::unique_ptr<Event> creation_completion_event_=std::make_unique<Event>();
 std::atomic<int> driver_calls{0};
 std::atomic<bool> render_pass_alive{true};
 bool CreatePipeline(const PipelineCreationArguments& a,VkShaderModule) {
   ++driver_calls;
   if(a.entered) a.entered->set_value();
   if(a.gate.valid()) a.gate.wait();
   assert(render_pass_alive);
   if(a.fail)return false;
   a.pipeline->second.pipeline=44;
   a.pipeline->second.pipeline_layout=a.layout;
   a.pipeline->second.is_placeholder=false;
   return true;
 }
 bool EnsurePipelineCreated(const PipelineCreationArguments&,VkShaderModule=0);
 void QueuePipelineCreation(const PipelineCreationArguments&);
 void CreationThread(size_t);
 void CreateQueuedPipelinesOnProcessorThread();
 void DrainPipelineCreation();
'''
TEST = r'''
int main() {
 VulkanPipelineCache c;
 using Status=VulkanPipelineCache::CreationStatus;
 VulkanPipelineCache::PipelineLayoutProvider layout{8};
 std::pair<int,VulkanPipelineCache::Pipeline> in_flight,queued,failed;
 std::promise<void> gate,entered;
 c.QueuePipelineCreation({&in_flight,&layout,false,gate.get_future().share(),&entered});
 std::thread worker([&]{c.CreationThread(0);});
 require(entered.get_future().wait_for(1s)==std::future_status::ready,"worker never began compiling");
 c.QueuePipelineCreation({&queued,&layout});
 auto draw=std::async(std::launch::async,[&]{
   VkPipeline p;const VulkanPipelineCache::PipelineLayoutProvider* l;bool pending;
   c.GetPipelineAndLayoutByHandle(&in_flight.second,p,l,&pending);
   return p==44 && l==&layout && !pending;
 });
 auto clear=std::async(std::launch::async,[&]{
   c.DrainPipelineCreation();c.render_pass_alive=false;
 });
 require(clear.wait_for(40ms)==std::future_status::timeout,"render-pass invalidation outran compiler");
 require(draw.wait_for(20ms)==std::future_status::timeout,"draw bypassed in-flight compilation");
 gate.set_value();
 require(draw.wait_for(1s)==std::future_status::ready && draw.get(),"worker completion lost draw");
 require(clear.wait_for(1s)==std::future_status::ready,"drain did not complete");clear.get();
 require(queued.second.creation_status==Status::kReady && c.driver_calls==2,"queue was lost or compiled twice");
 c.render_pass_alive=true;
 failed.second.pipeline=99;failed.second.pipeline_layout=&layout;failed.second.is_placeholder=true;
 c.QueuePipelineCreation({&failed,&layout,true});
 VkPipeline p;const VulkanPipelineCache::PipelineLayoutProvider* l;bool pending;
 c.GetPipelineAndLayoutByHandle(&failed.second,p,l,&pending);
 require(p==0 && l==nullptr && !pending && failed.second.creation_status==Status::kFailed,
         "compiler failure published placeholder as successful");
 c.DrainPipelineCreation();
 {std::lock_guard lock(c.creation_request_lock_);c.creation_threads_shutdown_from_=0;}
 c.creation_request_cond_.notify_all();worker.join();
 require(c.creation_threads_busy_==0,"worker did not leave cleanly");
 std::cout<<"PASS worker completion/failure, queue uniqueness, dependent-resource lifetime and shutdown\n";
}
'''
if __name__ == '__main__':
    print(generate(Path(sys.argv[1])))
