// Required original profile persistence policy. Project work: djultra64.
#ifdef NDEBUG
#undef NDEBUG
#endif
#include "port_profile_save.h"
#include <cassert>
#include <cstring>
#include <iostream>
using namespace fnr3::port;
static ProfileSaveObservation Ready(){
 ProfileSaveObservation s{};s.storage=0x2000;s.manager=0x4000;s.user=0;s.profile=0;
 s.state=-1;s.active_state=0;s.dirty=true;std::strcpy(s.name.data(),"djultra64");return s;
}
int main(){
 // Removing mandatory owner/profile, idle or bounded-name checks must fail here.
 for(int scenario=0;scenario<8;++scenario){
  RequiredProfileSaveSession session;auto s=Ready();
  if(scenario==0)s.user=-1;
  if(scenario==1)s.user=255;
  if(scenario==2)s.profile=4;
  if(scenario==3)s.storage=0;
  if(scenario==4)s.state=1;
  if(scenario==5)s.active_state=0x5000;
  if(scenario==6)s.name.fill('a');
  if(scenario==7)s.name.fill(0);
  assert(!session.Begin(s));assert(session.Observe(s)==ProfileSaveStatus::Invalid);
 }
 RequiredProfileSaveSession session;auto s=Ready();
 assert(session.Begin(s)); // Optional autosave setting is deliberately absent from policy.
 s.state=1;s.active_state=0x5000;
 assert(!session.Begin(s));assert(session.Observe(s)==ProfileSaveStatus::Pending);
 // Clearing dirty while the original writer remains busy cannot count as completion.
 s.dirty=false;assert(session.Observe(s)==ProfileSaveStatus::Pending);
 s.state=-1;s.active_state=0;
 assert(session.Observe(s)==ProfileSaveStatus::Success);
 s.dirty=true;assert(session.Observe(s)==ProfileSaveStatus::Failed);
 assert(session.Begin(s)); // Storage retry does not recommit/create another roster boxer.
 auto changed=s;changed.user=1;assert(session.Observe(changed)==ProfileSaveStatus::Invalid);
 changed=s;changed.profile=1;assert(session.Observe(changed)==ProfileSaveStatus::Invalid);
 changed=s;changed.name[0]='X';assert(session.Observe(changed)==ProfileSaveStatus::Invalid);
 changed=s;changed.storage+=4;assert(session.Observe(changed)==ProfileSaveStatus::Invalid);
 session.Reset();assert(session.Observe(s)==ProfileSaveStatus::Invalid);
 s.dirty=false;assert(session.Begin(s)); // Finishing an unchanged Edit still reaches the required writer.
 std::cout<<"PASS required save ownership, busy rejection, bounded names, retry and real completion policy\n";
}
#ifdef FNR3_PROFILE_SAVE_GUEST_CONTRACT
#include "port_apt.h"
#include <vector>
namespace {
constexpr uint32_t frontend=0x1000,userstate=0x2000,manager=0x10000,storage=0x3000;
constexpr uint32_t success=0x8000,failure=0x8100,stack_count=0x9000;
int starts=0,conversions=0;
void Arg(PPCContext& c,uint8_t*){c.r3.u64=c.r3.u32==0?success:failure;}
void String(PPCContext& c,uint8_t* b){++conversions;std::strcpy(reinterpret_cast<char*>(b+c.r4.u32),"[type Function]");}
void Front(PPCContext& c,uint8_t*){c.r3.u64=frontend;}
void User(PPCContext& c,uint8_t*){c.r3.u64=userstate;}
void Manager(PPCContext& c,uint8_t*){c.r3.u64=manager;}
void Select(PPCContext& c,uint8_t* b){assert(c.r3.u32==frontend&&c.r4.u32==0);WriteGuestWord(b,frontend+1176,c.r4.u32);}
void Name(PPCContext& c,uint8_t* b){assert(c.r3.u32==storage);std::strcpy(reinterpret_cast<char*>(b+storage+4560),reinterpret_cast<char*>(b+c.r4.u32));}
void Start(PPCContext& c,uint8_t* b){
 assert(c.r3.u32==storage&&c.r4.u32==1&&c.r5.u32==1);
 assert(b[storage+6352]==1&&b[storage+6353]==1);
 assert(ReadGuestWord(b,userstate)==0);
 assert(std::strcmp(reinterpret_cast<char*>(b+storage+5328),"[type Function]")==0);
 assert(std::strcmp(reinterpret_cast<char*>(b+storage+5584),"[type Function]")==0);
 ++starts;WriteGuestWord(b,storage+4488,1);WriteGuestWord(b,storage+4496,0x7000);
 c.lr=0;c.r31.u64=0;
}
const ProfileSaveGuestApi api{Arg,String,Front,User,Manager,Select,Name,Start,stack_count};
void Init(std::vector<uint8_t>& memory){
 std::fill(memory.begin(),memory.end(),0);auto* b=memory.data();
 WriteGuestWord(b,frontend+1160,storage);WriteGuestWord(b,userstate+3356,0);
 WriteGuestWord(b,storage+4488,0xffffffff);WriteGuestWord(b,storage+4496,0);
 WriteGuestWord(b,storage+4504,0x7000);
 WriteGuestWord(b,manager+536+14316,1);
 std::strcpy(reinterpret_cast<char*>(b+manager+536+14292),"djultra64");
 WriteGuestWord(b,success+4,0x08000022);WriteGuestWord(b,failure+4,0x08000024);
 WriteGuestWord(b,stack_count,2);
 // A disabled optional autosave preference is separate memory and remains untouched.
 WriteGuestWord(b,0x9500,0);
}
struct GuestContract {
 GuestContract(){
  std::vector<uint8_t> memory(0x40000);Init(memory);auto* b=memory.data();
  PPCContext c{};c.r1.u64=0x3f000;c.r3.u64=0x1200;c.r4.u64=2;c.lr=0x123456;c.r31.u64=0xabcdef;
  const auto before=c;RequiredProfileSaveSession session;
  assert(StartRequiredProfileSave(c,b,api,session));
  assert(starts==1&&ReadGuestWord(b,0x9500)==0);
  assert(std::strcmp(reinterpret_cast<char*>(b+storage+4560),"djultra64")==0);
  assert(c.r1.u64==before.r1.u64&&c.r3.u64==before.r3.u64&&c.r4.u64==before.r4.u64&&c.lr==before.lr&&c.r31.u64==before.r31.u64);
  assert(!StartRequiredProfileSave(c,b,api,session)&&starts==1);
  assert(ReadRequiredProfileSaveStatus(c,b,api,session)==ProfileSaveStatus::Pending);
  WriteGuestWord(b,storage+4488,0xffffffff);WriteGuestWord(b,storage+4496,0);
 WriteGuestWord(b,storage+4504,0x7000);
  assert(ReadRequiredProfileSaveStatus(c,b,api,session)==ProfileSaveStatus::Failed);
  WriteGuestWord(b,manager+536+14316,0);
  assert(ReadRequiredProfileSaveStatus(c,b,api,session)==ProfileSaveStatus::Success);
  WriteGuestWord(b,userstate+3356,1);
  assert(ReadRequiredProfileSaveStatus(c,b,api,session)==ProfileSaveStatus::Invalid);
  for(int invalid=0;invalid<11;++invalid){
   Init(memory);RequiredProfileSaveSession fresh;const int count=starts;
   WriteGuestWord(b,manager+536+14316,0);
   if(invalid==0)WriteGuestWord(b,userstate+3356,0xffffffff);
   if(invalid==1)b[manager+361]=4;
   if(invalid==2)WriteGuestWord(b,storage+4488,1);
   if(invalid==3)std::memset(b+manager+536+14292,'a',256);
   if(invalid==4)WriteGuestWord(b,success+4,0x08000007);
   if(invalid==5)WriteGuestWord(b,failure+4,0x00000022);
   if(invalid==6)WriteGuestWord(b,stack_count,1);
   if(invalid==7)WriteGuestWord(b,frontend+1160,0);
   if(invalid==8)WriteGuestWord(b,storage+4504,0);
   if(invalid==9)b[manager+536+14292]=0;
   if(invalid==10)c.r4.u64=1;
   const auto dirty_before=ReadGuestWord(b,manager+536+14316);
   assert(!StartRequiredProfileSave(c,b,api,fresh)&&starts==count);
   assert(b[storage+6352]==0); // Rejected input never partially starts storage.
   assert(ReadGuestWord(b,manager+536+14316)==dirty_before);
   c.r4.u64=2;
  }
  Init(memory);WriteGuestWord(b,manager+536+14316,0);RequiredProfileSaveSession unchanged;
  assert(StartRequiredProfileSave(c,b,api,unchanged));
  assert(ReadGuestWord(b,manager+536+14316)==1); // Failed/cancelled unchanged saves cannot masquerade as success.
  std::cout<<"PASS original guest API handoff, disabled preference, callbacks, context and validation\n";
 }
} guest_contract;
}
// The production overload binds these exact symbols; tests replace only original
// guest calls, while exercising all real bridge memory validation/mutations.
extern "C" {
void sub_82391F50(PPCContext& c,uint8_t* b){Arg(c,b);}
void sub_82399900(PPCContext& c,uint8_t* b){String(c,b);}
void sub_82295C80(PPCContext& c,uint8_t* b){Front(c,b);}
void sub_82317C98(PPCContext& c,uint8_t* b){User(c,b);}
void sub_8228AE78(PPCContext& c,uint8_t* b){Manager(c,b);}
void sub_823192A0(PPCContext& c,uint8_t* b){Select(c,b);}
void sub_8231A190(PPCContext& c,uint8_t* b){Name(c,b);}
void sub_8231A338(PPCContext& c,uint8_t* b){Start(c,b);}
}
#endif
