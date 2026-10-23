// Native APT settings transactions. Work: djultra64.
#ifdef NDEBUG
#undef NDEBUG
#endif
#include "port_native_graphics.h"
#include <cassert>
#include <iostream>
using namespace fnr3::port;
int main(){
 NativeGraphicsSession s;
 bool threw=false;try{(void)s.Get(0);}catch(const std::logic_error&){threw=true;}assert(threw);
 PortSettings initial;initial.graphics={"1080p","fxaa","8x",false};initial.input_family="switch";
 initial.bindings.Bind(InputAction::Confirm,PhysicalButton::East);
 s.Begin(initial);assert(s.Get(0)==2&&s.Get(1)==0&&s.Get(2)==1&&s.Get(3)==4&&s.Get(4)==3);
 assert(s.Get(5)==1);s.Step(5,1);assert(s.Get(5)==0&&s.Pending().graphics.frame_rate==30);
 s.Step(5,-1);assert(s.Get(5)==1&&s.Pending().graphics.frame_rate==60);
 s.Step(0,-1);assert(s.Get(0)==1);s.Step(1,-1);assert(s.Get(1)==1);
 for(int i=0;i<3;++i)s.Step(2,1);assert(s.Get(2)==1);
 s.Step(4,1);assert(s.Get(4)==0);
 assert(s.Pending().bindings.physical==initial.bindings.physical);
 threw=false;try{s.Step(6,1);}catch(const std::invalid_argument&){threw=true;}assert(threw);
 threw=false;try{s.Step(0,8);}catch(const std::invalid_argument&){threw=true;}assert(threw);
 assert(s.Get(0)==1);
 auto before=s.Pending();bool wrote=false;
 try{s.Save([&](const PortSettings&){wrote=true;throw std::runtime_error("disk full");});assert(false);}catch(const std::runtime_error&){}
 assert(wrote&&s.Get(0)==1);PortSettings saved;
 s.Save([&](const PortSettings& p){saved=p;});assert(saved.graphics.resolution=="900p"&&saved.graphics.fullscreen);
 assert(saved.bindings.physical==initial.bindings.physical);
 s.StepBinding(0,1);assert(s.GetBinding(0)==2&&s.GetBinding(2)==1);
 s.StepBinding(0,-1);assert(s.GetBinding(0)==1);
 s.ResetBindings();for(unsigned i=0;i<kActionCount;++i)assert(s.GetBinding(i)==int(i));
 s.Step(0,1);s.Cancel();assert(!s.Active());s.Begin(saved);assert(s.Get(0)==1);
 for(int field=0;field<6;++field){auto n=s.Count(field);for(int v=0;v<n;++v){auto old=s.Get(field);s.Step(field,1);assert(s.Get(field)==(old+1)%n);} }
 std::cout<<"PASS native graphics finite values, wrap, draft/cancel/save, failed persistence and input preservation\n";
}
