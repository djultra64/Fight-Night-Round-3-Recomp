// Exact APT object scope and PPC context lifetime. Project work: djultra64.
#ifdef NDEBUG
#undef NDEBUG
#endif
#include "port_apt.h"
#include <array>
#include <cassert>
#include <iostream>
using namespace fnr3::port;
static bool fail_allocation=false,registered=false;
void Allocate(PPCContext& c,uint8_t*){assert(c.r3.u32==123&&c.r4.u32==36);c.r3.u64=fail_allocation?0:512;}
void Construct(PPCContext& c,uint8_t*){assert(c.r3.u32==512&&c.r4.u32==777);c.r4.u64=0;}
void Register(PPCContext& c,uint8_t*){assert(c.r3.u32==888&&c.r4.u32==64&&c.r5.u32==512);registered=true;c.lr=0;c.r31.u64=0;}
static int argument_calls=0,conversion_calls=0,factory_calls=0;
void Argument(PPCContext& c,uint8_t*){assert(c.r3.u32==0);++argument_calls;c.r3.u64=768;c.lr=0;c.r31.u64=0;}
void Integer(PPCContext& c,uint8_t*){assert(c.r3.u32==768);++conversion_calls;c.r3.s64=-19;c.lr=0;}
void MakeInteger(PPCContext& c,uint8_t*){assert(c.r3.s32==-23);++factory_calls;c.r3.u64=900;c.r31.u64=0;c.lr=0;}
int main(){
 std::array<uint8_t,4096> memory{};auto* b=memory.data();
 AptApi api{Allocate,Construct,Register,16,20,0x12345678,0x23456789};
 WriteGuestWord(b,16,123);WriteGuestWord(b,20,128);
 WriteGuestWord(b,128,api.function_vtable);WriteGuestWord(b,160,api.original_noop);
 // Another method shares the noop and must stay untouched.
 WriteGuestWord(b,256,api.function_vtable);WriteGuestWord(b,288,api.original_noop);
 PPCContext c{};c.lr=0x11111111;c.r31.u64=0x2222222233333333;c.r3.u64=99;
 fail_allocation=true;bool rejected=false;
 try{BindAptHostActions(c,b,888,api,666,777,64);}catch(const std::runtime_error&){rejected=true;}
 assert(rejected&&!registered&&ReadGuestWord(b,160)==api.original_noop);
 fail_allocation=false;BindAptHostActions(c,b,888,api,666,777,64);
 assert(registered&&ReadGuestWord(b,160)==666&&ReadGuestWord(b,288)==api.original_noop);
 assert(c.lr==0x11111111&&c.r31.u64==0x2222222233333333&&c.r3.u32==99);
 // General registration creates an independent function using the same original API.
 registered=false;const auto object=RegisterAptHostMethod(c,b,888,api,777,64);
 assert(object==512&&registered&&ReadGuestWord(b,160)==666);
 assert(c.lr==0x11111111&&c.r31.u64==0x2222222233333333&&c.r3.u32==99);
 AptValueApi values{Argument,Integer,MakeInteger,24};
 WriteGuestWord(b,24,1);WriteGuestWord(b,772,0x08000007);
 c.r4.u64=1;const auto before=c;
 assert(ReadAptIntegerArgument(c,b,values)==-19);
 assert(argument_calls==1&&conversion_calls==1);
 assert(c.r3.u64==before.r3.u64&&c.r4.u64==before.r4.u64&&c.lr==before.lr&&c.r31.u64==before.r31.u64);
 assert(ReadGuestWord(b,772)==0x08000007); // borrowed value: no refcount or flag changes
 for(auto flags: {0x08000005u,0x00000007u}){
  WriteGuestWord(b,772,flags);assert(!ReadAptIntegerArgument(c,b,values));
 }
 assert(conversion_calls==1);
 c.r4.u64=0;assert(!ReadAptIntegerArgument(c,b,values));
 c.r4.u64=2;assert(!ReadAptIntegerArgument(c,b,values));
 c.r4.u64=1;WriteGuestWord(b,24,0);assert(!ReadAptIntegerArgument(c,b,values));
 MakeAptIntegerResult(c,b,-23,values);
 assert(factory_calls==1&&c.r3.u32==900&&c.lr==before.lr&&c.r31.u64==before.r31.u64);
 // A second initialization can safely retain the same scoped Quit binding.
 BindAptHostActions(c,b,888,api,666,777,64);
 WriteGuestWord(b,160,0xDEADBEEF);rejected=false;
 try{BindAptHostActions(c,b,888,api,666,777,64);}catch(const std::runtime_error&){rejected=true;}
 assert(rejected&&ReadGuestWord(b,288)==api.original_noop);
 std::cout<<"PASS scoped native Quit object, original script API and return-context preservation\n";
}
