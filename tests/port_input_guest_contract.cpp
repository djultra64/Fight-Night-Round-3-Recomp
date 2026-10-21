// Real guest wrapper contract; no runtime/window/device creation. Work: djultra64.
#include "port_input.h"
#include <rex/ppc/context.h>
#include <rex/types.h>
#include <array>
#include <cstdlib>
#include <iostream>
using namespace fnr3::port;
namespace {uint32_t status=0;void check(bool c,const char* m){if(!c){std::cerr<<m<<'\n';std::exit(1);}}}
extern "C" void __imp__sub_8251AA38(PPCContext& ctx,uint8_t*){ctx.r3.u32=status;}
extern "C" void sub_8251AA38(PPCContext&,uint8_t*);
int main(){
 // Automatic preview must use detected hardware even while a manual family
 // is selected; the real observer begins with Xbox until a device is active.
 check(DetectedInputFamily()==InputFamily::Xbox,"Initial detected family");
 SelectInputFamily(InputFamily::PlayStation);
 check(ActiveInputFamily()==InputFamily::PlayStation,"Manual effective family");
 check(DetectedInputFamily()==InputFamily::Xbox,"Detection is independent of manual selection");
 SelectInputFamily(InputFamily::Automatic);
 std::array<uint8_t,4096> memory{};PPCContext ctx{};
 auto& buttons=*reinterpret_cast<rex::be<uint16_t>*>(memory.data()+0x104);
 auto& packet=*reinterpret_cast<rex::be<uint32_t>*>(memory.data()+0x100);
 auto poll=[&](uint16_t b,uint32_t user=0){ctx.r4.u32=0x100;ctx.r3.u32=user;buttons=b;packet=42;sub_8251AA38(ctx,memory.data());return uint16_t(buttons);};
 memory[0x106]=231;memory[0x107]=157;memory[0x108]=0x12;
 check(poll(0x1000)==0x1000,"Default guest mapping");
 check(uint32_t(packet)==42,"Default packet unchanged");
 check(memory[0x106]==231&&memory[0x107]==157&&memory[0x108]==0x12,"Triggers/axes unchanged");
 BindAction(InputAction::Confirm,PhysicalButton::East);
 check(poll(0x2000)==0x1000,"Guest action remap actually reaches returned state");
 check(uint32_t(packet)==43,"Binding revision changes packet");
 SuppressHeldInputButtons();
 check(poll(0x2000)==0,"Save suppresses held physical button without capturing the menu");
 check(!HostInputCaptured(),"Save must not leave persistent capture");
 check(poll(0)==0,"Save physical release");
 check(poll(0x2000)==0x1000,"Next press after Save reaches guest");
 SetHostInputCapture(true);check(poll(0x2010)==0,"Capture removes guest buttons");
 for(unsigned i=0x104;i<0x110;++i)check(memory[i]==0,"Capture removes all controls");
 check(poll(0,1)==0,"Second player idle while host captures");
 SetHostInputCapture(false);check(poll(0x2010)==0,"Host close release barrier");
 check(poll(0)==0,"Physical release");check(poll(0x2000)==0x1000,"Next press rearmed");
 status=1167;check(poll(0x2000)==0x2000,"Failed import leaves state untouched");
 ctx.r4.u32=0;status=0;sub_8251AA38(ctx,memory.data());check(ctx.r3.u32==0,"Null state query preserved");
 std::cout<<"guest input wrapper contract passed\n";
}
