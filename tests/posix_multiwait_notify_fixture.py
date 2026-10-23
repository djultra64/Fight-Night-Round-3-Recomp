"""Generate a private POSIX wait regression fixture from the supplied SDK.

Work: djultra64. SDK implementation is extracted at execution, never vendored.
Usage: python tests/posix_multiwait_notify_fixture.py SDK_ROOT OUTPUT.cpp
Compile/run the generated fixture only on the authorized build host:
clang++ -std=c++23 -O2 -pthread OUTPUT.cpp -o OUTPUT && timeout 30 OUTPUT

Exercises real condition implementations. The timer queue uses a purpose-written
host scheduler seam. Thread completion tests extract the production publication
blocks, without creating/cancelling SDK threads or testing their lifecycle.
The latency regression checks median signal-to-return delay, not source spelling.
"""
from pathlib import Path
import sys


def block(text, start):
    begin = text.index('{', start)
    depth, end = 1, begin + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[begin:end]


def generate(sdk):
    source = (sdk / 'src/core/threading_posix.cpp').read_text()
    first = source.index('class PosixConditionBase {')
    # The production wake registry, if present, is kept intact.
    helper_start = source.rfind('// Multi-wait', 0, first)
    helpers = source[helper_start:first] if helper_start >= 0 else ''
    classes = source[first:source.index('struct ThreadStartData {', first)]
    terminate_start = source.index('  void Terminate(int exit_code) {')
    terminate_lock = source.index('    {\n      std::lock_guard<std::mutex> lock(mutex_);', terminate_start)
    terminate = block(source, terminate_lock)
    natural_start = source.index('    std::unique_lock<std::mutex> lock(thread->handle_.mutex_);')
    natural = block(source, source.rfind('  {', 0, natural_start)).replace('thread->handle_.', '')
    completion = r'''
class Completion : public PosixConditionBase {
 public:
 bool Signal() override { Terminate(0); return true; }
 void Terminate(int exit_code) TERMINATE
 void Natural() NATURAL
 private:
 bool signaled() const override { return signaled_; }
 void post_execution() override {}
 bool signaled_ = false;
 int exit_code_ = -1;
};
'''.replace('TERMINATE', terminate).replace('NATURAL', natural)
    return PREFIX + helpers + classes + completion + SUFFIX


PREFIX = r'''
#include <algorithm>
#include <atomic>
#include <cassert>
#include <cerrno>
#include <chrono>
#include <condition_variable>
#include <cstdint>
#include <cstdlib>
#include <functional>
#include <future>
#include <iostream>
#include <limits>
#include <memory>
#include <mutex>
#include <pthread.h>
#include <thread>
#include <utility>
#include <vector>
#define REX_PLATFORM_LINUX 1
#define assert_true(x) assert(x)
#define assert_not_null(x) assert(x)
#define assert_always() assert(false)
using namespace std::chrono_literals;
using Clock = std::chrono::steady_clock;
enum class WaitResult { kSuccess, kFailed, kTimeout };
struct Event {}; struct Semaphore {}; struct Mutant {}; struct Timer {};
// Host scheduling seam: production Timer::CompletionRoutine and Signal are
// extracted unchanged. Disarm joins pending/running callbacks like the SDK API.
struct TimerQueueWaitItem {
 std::mutex mutex; std::condition_variable cv; bool stop = false; std::thread worker;
 void Disarm() { {std::lock_guard lock(mutex); stop = true;} cv.notify_all();
   if(worker.joinable()) worker.join(); }
 ~TimerQueueWaitItem() { Disarm(); }
};
std::vector<std::shared_ptr<TimerQueueWaitItem>> timer_items;
std::weak_ptr<TimerQueueWaitItem> QueueTimerRecurring(std::function<void(void*)> cb,
 void* arg, Clock::time_point due, Clock::duration period) {
 auto item = std::make_shared<TimerQueueWaitItem>();
 item->worker = std::thread([p=item.get(),cb,arg,due,period]() mutable {
  std::unique_lock lock(p->mutex);
  while(!p->cv.wait_until(lock,due,[&]{return p->stop;})) {
   lock.unlock(); cb(arg); lock.lock(); if(period == Clock::duration::zero()) break; due += period;
  }
 }); timer_items.push_back(item); return item;
}
std::weak_ptr<TimerQueueWaitItem> QueueTimerOnce(std::function<void(void*)> cb,
 void* arg, Clock::time_point due) { return QueueTimerRecurring(cb,arg,due,Clock::duration::zero()); }
void require(bool ok, const char* label) {
 if(!ok) {std::cerr << "FAIL " << label << '\n'; std::exit(1);}
}
'''

SUFFIX = r'''
using Base = PosixConditionBase;
using E = PosixCondition<Event>; using S = PosixCondition<Semaphore>;
using M = PosixCondition<Mutant>; using T = PosixCondition<Timer>;
auto multi(std::initializer_list<Base*> handles, bool all=false,
 std::chrono::milliseconds timeout=100ms) {
 return Base::WaitMultiple(std::vector<Base*>(handles),all,timeout);
}
auto prompt_multi(std::initializer_list<Base*> handles, const char* label) {
 auto start=Clock::now();auto result=multi(handles);
 require(Clock::now()-start<50ms,label);return result;
}
class RobustProbe : public Base {
 public:
 bool Signal() override {return true;}
 void Abandon() {require(pthread_mutex_lock(mutex_.native_handle())==0,"robust owner locks");}
 void PublishAndAbandon() {Abandon(); ready_=true;}
 void MakeUnready() {ready_=false;}
 std::atomic<bool> predicate_seen=false;
 private:
 bool signaled() const override {const_cast<RobustProbe*>(this)->predicate_seen=true;return ready_;}
 void post_execution() override {}
 bool ready_=true;
};
void semantic_tests() {
 {E a(true,true), b(true,true); auto r=multi({&a,&b});
  require(r.first==WaitResult::kSuccess && r.second==0,"wait-any lowest index");
  require(a.Wait(0ms)==WaitResult::kSuccess,"manual event remains signaled");
  a.Reset(); require(a.Wait(0ms)==WaitResult::kTimeout,"manual reset");}
 {E a(false,true), b(false,false); require(multi({&a,&b},true,0ms).first==WaitResult::kTimeout,"wait-all zero timeout");
  require(a.Wait(0ms)==WaitResult::kSuccess,"failed wait-all preserves auto event");
  a.Signal(); b.Signal();require(multi({&a,&b},true).first==WaitResult::kSuccess,"wait-all success");
  require(a.Wait(0ms)==WaitResult::kTimeout && b.Wait(0ms)==WaitResult::kTimeout,"wait-all atomic consumption");}
 {S s(0,2); E e(true,false); int prev=-1;
  require(s.Release(2,&prev)&&prev==0,"semaphore previous count");
  require(!s.Release(1,nullptr),"semaphore overflow rejected");
  require(multi({&s,&e}).first==WaitResult::kSuccess && multi({&s,&e}).first==WaitResult::kSuccess,"semaphore consumes one per wait");
  require(multi({&s,&e},false,0ms).first==WaitResult::kTimeout,"semaphore exhausted");}
 {M m(false); E e(true,false); require(multi({&m,&e}).first==WaitResult::kSuccess,"mutant acquisition");
  require(multi({&m,&e}).first==WaitResult::kSuccess,"mutant recursive owner");
  require(m.Release()&&m.Release(),"mutant recursion releases");
  std::atomic<bool> acquired=false;
  require(m.Wait(0ms)==WaitResult::kSuccess,"mutant owned before cross-thread wait");
  std::thread waiter([&]{acquired=multi({&m,&e}).first==WaitResult::kSuccess; if(acquired)m.Release();});
  std::this_thread::sleep_for(2ms);require(!acquired,"mutant excludes other owner");auto released=Clock::now();m.Release();waiter.join();require(acquired && Clock::now()-released<50ms,"mutant release wakes multiwait promptly");}
 {E a(true,false),b(true,false);auto start=Clock::now();
  require(multi({&a,&b},false,3ms).first==WaitResult::kTimeout,"finite timeout result");
  auto elapsed=Clock::now()-start;require(elapsed>=3ms && elapsed<100ms,"finite steady deadline");
  std::thread producer([&]{std::this_thread::sleep_for(1ms);b.Signal();});
  auto r=multi({&a,&b},false,std::chrono::milliseconds::max());producer.join();
  require(r.first==WaitResult::kSuccess && r.second==1,"infinite wait wake");}
 {T timer(false); E e(true,false); std::atomic<int> callbacks=0;
  timer.SetOnce(Clock::now()+2ms,[&]{++callbacks;});
  require(prompt_multi({&timer,&e},"timer wake notification").first==WaitResult::kSuccess,"timer completion wakes multiwait");timer.Cancel();
  require(callbacks==1 && timer.Wait(0ms)==WaitResult::kTimeout,"auto timer callback and consumption");
  timer.SetRepeating(Clock::now()+1ms,1ms,nullptr);
  require(multi({&timer,&e}).first==WaitResult::kSuccess && multi({&timer,&e}).first==WaitResult::kSuccess,"recurring timer progress");timer.Cancel();}
 {T timer(true);E e(true,false);timer.SetOnce(Clock::now()+1ms,nullptr);
  require(multi({&timer,&e}).first==WaitResult::kSuccess && multi({&timer,&e},false,0ms).first==WaitResult::kSuccess,"manual timer remains signaled");timer.Cancel();}
 for(bool natural:{false,true}) {Completion c;E e(true,false);
  std::thread producer([&]{std::this_thread::sleep_for(1ms);if(natural)c.Natural();else c.Terminate(7);});
  require(prompt_multi({&c,&e},"thread exit wake notification").first==WaitResult::kSuccess,"thread exit publication wakes multiwait");producer.join();
  require(c.Wait(0ms)==WaitResult::kSuccess,"thread exit remains signaled");}
 {S semaphore(0,3);E unused(true,false);
  std::thread producer([&]{std::this_thread::sleep_for(1ms);semaphore.Release(1,nullptr);});
  require(prompt_multi({&semaphore,&unused},"semaphore release wake notification").first==WaitResult::kSuccess,"semaphore async release");producer.join();}
 {RobustProbe probe; E unused(true,false);std::thread owner([&]{probe.Abandon();});owner.join();
  require(multi({&probe,&unused}).first==WaitResult::kSuccess,"robust owner death recovery");}
 // Once parked, an owner may publish readiness and die before notifying.
 // Robust-mutex recovery must make progress without a normal signal publisher.
 {RobustProbe probe;probe.MakeUnready();E rescue(true,false);
  auto start=Clock::now();std::thread owner([&]{
   while(!probe.predicate_seen.load())std::this_thread::yield();
   std::this_thread::sleep_for(2ms);probe.PublishAndAbandon();});
  std::thread watchdog([&]{std::this_thread::sleep_for(100ms);rescue.Signal();});
  auto result=multi({&probe,&rescue},false,std::chrono::milliseconds::max());
  auto elapsed=Clock::now()-start;owner.join();watchdog.join();
  require(result.first==WaitResult::kSuccess && result.second==0 && elapsed<50ms,
          "parked multiwait did not recover robust owner death without notification");}
 // Broadcast must wake every observer of a manual event; auto events are consumed once.
 {E event(true,false),unused(true,false);std::atomic<int> entered=0,completed=0;std::vector<std::thread> waiters;
  for(int i=0;i<8;++i)waiters.emplace_back([&]{++entered;if(prompt_multi({&event,&unused},"manual event broadcast notification").first==WaitResult::kSuccess)++completed;});
  while(entered!=8)std::this_thread::yield();std::this_thread::sleep_for(2ms);event.Signal();
  for(auto& thread:waiters)thread.join();require(completed==8,"manual event wakes all observers");}
 // Repeated concurrent wait-all cannot consume one component while another is missing.
 {E a(false,true),b(false,false);for(int i=0;i<50;++i)require(multi({&a,&b},true,0ms).first==WaitResult::kTimeout,"wait-all no partial consumption stress");
  require(a.Wait(0ms)==WaitResult::kSuccess,"wait-all preserves component after stress");}
 // Signals at all phases of snapshot, predicate check and sleep must make progress.
 {E request(false,false),ack(false,false),unused(true,false);constexpr int count=1500;
  std::thread producer([&]{for(int i=0;i<count;++i){request.Signal();require(ack.Wait(1s)==WaitResult::kSuccess,"stress ack progress");}});
  for(int i=0;i<count;++i){require(multi({&unused,&request},false,std::chrono::milliseconds::max()).first==WaitResult::kSuccess,"stress no lost notification");ack.Signal();}producer.join();}
 std::cout << "PASS condition semantics, timers, completion publications, stress\n";
}
void latency_regression() {
 E request(false,false),ack(false,false),unused(true,false);std::atomic<bool> ready=false;
 std::atomic<int64_t> sent=0;std::vector<int64_t> latencies;
 std::thread producer([&]{for(int i=0;i<101;++i){while(!ready.load(std::memory_order_acquire))std::this_thread::yield();
  ready.store(false,std::memory_order_release);std::this_thread::sleep_for(200us);
  sent.store(Clock::now().time_since_epoch().count(),std::memory_order_release);request.Signal();
  require(ack.Wait(1s)==WaitResult::kSuccess,"latency ack");}});
 for(int i=0;i<101;++i){ready.store(true,std::memory_order_release);
  require(multi({&unused,&request}).first==WaitResult::kSuccess,"latency progress");
  auto elapsed=Clock::now().time_since_epoch()-Clock::duration(sent.load(std::memory_order_acquire));
  latencies.push_back(std::chrono::duration_cast<std::chrono::microseconds>(elapsed).count());ack.Signal();}
 producer.join();std::sort(latencies.begin(),latencies.end());
 std::cout<<"signal_to_multiwait_return_median_us="<<latencies[50]<<" p95_us="<<latencies[95]<<'\n';
 require(latencies[50]<500,"multiwait retains millisecond polling latency");
}
int main(){semantic_tests();latency_regression();for(auto& item:timer_items)item->Disarm();std::cout<<"PASS multiwait notification regression\n";}
'''

if __name__ == '__main__':
    Path(sys.argv[2]).write_text(generate(Path(sys.argv[1])))
