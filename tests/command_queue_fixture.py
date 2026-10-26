"""Run real command-processor dispatch with concurrent producers and reentrant tasks.
Work: djultra64. Generate C++23 source from the prepared SDK.
"""
from pathlib import Path
import sys
from pipeline_completion_fixture import extract

PREFIX = r'''
#include <atomic>
#include <cassert>
#include <functional>
#include <iostream>
#include <memory>
#include <mutex>
#include <queue>
#include <thread>
#include <vector>
namespace system_fake { struct XThread { static thread_local bool active;
 static bool IsInThread(void*){return active;} };thread_local bool XThread::active=false; }
struct Event {void Set(){}};
struct CommandProcessor {
 std::mutex pending_fns_mutex_;
 std::atomic<bool> pending_fns_available_{false};
 std::queue<std::function<void()>> pending_fns_;
 std::unique_ptr<int> worker_thread_;
 std::unique_ptr<Event> write_ptr_index_event_=std::make_unique<Event>();
 void CallInThread(std::function<void()>);void RunPendingFunctions();
};
'''
TEST=r'''
int main(){
 CommandProcessor c;
 std::vector<int> order;
 c.CallInThread([&]{order.push_back(1);c.CallInThread([&]{order.push_back(3);});});
 c.CallInThread([&]{order.push_back(2);});
 system_fake::XThread::active=true;c.RunPendingFunctions();system_fake::XThread::active=false;
 assert((order==std::vector<int>{1,2,3}));
 std::atomic<int> done=0;std::vector<int> last(8,-1);
 std::thread worker([&]{system_fake::XThread::active=true;
   while(done!=8000){c.RunPendingFunctions();std::this_thread::yield();}
 });
 std::vector<std::thread> producers;
 for(int i=0;i<8;++i)producers.emplace_back([&,i]{
   for(int j=0;j<1000;++j)c.CallInThread([&,i,j]{assert(last[i]+1==j);last[i]=j;++done;});
 });
 for(auto& t:producers)t.join();worker.join();
 assert(!c.pending_fns_available_ && c.pending_fns_.empty());
 std::cout<<"PASS concurrent dispatch, FIFO, callback reentry and no lost tasks\n";
}
'''
def generate(sdk):
    source=(sdk/'src/graphics/command_processor.cpp').read_text()
    return PREFIX+'\n'.join(extract(source,s).replace('system::XThread','system_fake::XThread') for s in ('void CommandProcessor::CallInThread(', 'void CommandProcessor::RunPendingFunctions('))+TEST
if __name__=='__main__':print(generate(Path(sys.argv[1])))
