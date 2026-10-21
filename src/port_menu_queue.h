// Lifecycle-safe, event-only UI handoff. Project work: djultra64.
#pragma once
#include <atomic>
#include <functional>
#include <memory>
namespace fnr3::port {
enum class MenuAction : unsigned { Quit=1, Graphics=2, Restart=4 };
class MenuQueue {
public:
 using Post=std::function<bool(std::function<void()>)>;
 using Handler=std::function<void(MenuAction)>;
 static std::shared_ptr<MenuQueue> Create(Post post,Handler handler){
   return std::shared_ptr<MenuQueue>(new MenuQueue(std::move(post),std::move(handler)));
 }
 bool Request(MenuAction action){
   auto state=state_;const auto bit=unsigned(action);
   if(!state->active.load(std::memory_order_acquire))return false;
   auto old=state->pending.load();
   do{
     if(old&bit || (action!=MenuAction::Quit && (old&unsigned(MenuAction::Quit))) || (action==MenuAction::Graphics && (old&unsigned(MenuAction::Restart))))return false;
   }while(!state->pending.compare_exchange_weak(old,old|bit));
   auto work=[state,action,bit]{
     if(!state->active.load(std::memory_order_acquire))return;
     if(action==MenuAction::Graphics){
       state->pending.fetch_and(~bit);
       if(state->pending.load()&(unsigned(MenuAction::Quit)|unsigned(MenuAction::Restart)))return;
     }
     if(action==MenuAction::Restart && (state->pending.load()&unsigned(MenuAction::Quit)))return;
     state->handler(action);
   };
   try{
     if(state->post(std::move(work)))return true;
   }catch(...){state->pending.fetch_and(~bit);throw;}
   state->pending.fetch_and(~bit);return false;
 }
 void Shutdown(){state_->active.store(false,std::memory_order_release);}
 ~MenuQueue(){Shutdown();}
private:
 struct State{std::atomic<bool> active{true};std::atomic<unsigned> pending{0};Post post;Handler handler;};
 MenuQueue(Post post,Handler handler):state_(std::make_shared<State>()){
   state_->post=std::move(post);state_->handler=std::move(handler);
 }
 std::shared_ptr<State> state_;
};
} // namespace fnr3::port
