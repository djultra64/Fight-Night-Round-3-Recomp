// Menu lifecycle contract. Project work: djultra64.
#ifdef NDEBUG
#undef NDEBUG
#endif
#include "port_menu_queue.h"
#include <cassert>
#include <iostream>
#include <vector>
using namespace fnr3::port;
int main(){
 std::vector<std::function<void()>> pending;std::vector<MenuAction> delivered;
 auto queue=MenuQueue::Create([&](auto f){pending.push_back(std::move(f));return true;},[&](auto action){delivered.push_back(action);});
 assert(queue->Request(MenuAction::Graphics));
 assert(!queue->Request(MenuAction::Graphics));
 assert(pending.size()==1);pending.back()();pending.clear();
 assert(delivered==std::vector{MenuAction::Graphics});
 assert(queue->Request(MenuAction::Graphics));queue->Shutdown();
 pending.back()();pending.clear();assert(delivered.size()==1);
 assert(!queue->Request(MenuAction::Quit));
 auto quitting=MenuQueue::Create([&](auto f){pending.push_back(std::move(f));return true;},[&](auto action){delivered.push_back(action);});
 assert(quitting->Request(MenuAction::Graphics));assert(quitting->Request(MenuAction::Quit));
 assert(!quitting->Request(MenuAction::Graphics));
 for(auto& f:pending)f();pending.clear();
 assert(delivered==std::vector({MenuAction::Graphics,MenuAction::Quit}));
 assert(!quitting->Request(MenuAction::Quit));
 delivered.clear();
 auto restarting=MenuQueue::Create([&](auto f){pending.push_back(std::move(f));return true;},[&](auto action){delivered.push_back(action);});
 assert(restarting->Request(MenuAction::Graphics));assert(restarting->Request(MenuAction::Restart));
 assert(!restarting->Request(MenuAction::Restart));assert(!restarting->Request(MenuAction::Graphics));
 for(auto& f:pending)f();pending.clear();assert(delivered==std::vector{MenuAction::Restart});
 delivered.clear();
 auto both=MenuQueue::Create([&](auto f){pending.push_back(std::move(f));return true;},[&](auto action){delivered.push_back(action);});
 assert(both->Request(MenuAction::Restart));assert(both->Request(MenuAction::Quit));
 for(auto& f:pending)f();pending.clear();assert(delivered==std::vector{MenuAction::Quit});
 auto dropped=MenuQueue::Create([](auto){return false;},[](auto){assert(false);});
 assert(!dropped->Request(MenuAction::Quit));assert(!dropped->Request(MenuAction::Quit));
 std::cout<<"PASS deferred UI dispatch, coalescing, shutdown cancellation and quit priority\n";
}
