// Required original profile writer bridge. Project work: djultra64.
#include "port_profile_save.h"
#include "port_apt.h"
#include <algorithm>
#include <limits>
extern "C" {
void sub_82391F50(PPCContext&,uint8_t*);
void sub_82399900(PPCContext&,uint8_t*);
void sub_82295C80(PPCContext&,uint8_t*);
void sub_82317C98(PPCContext&,uint8_t*);
void sub_8228AE78(PPCContext&,uint8_t*);
void sub_823192A0(PPCContext&,uint8_t*);
void sub_8231A190(PPCContext&,uint8_t*);
void sub_8231A338(PPCContext&,uint8_t*);
}
namespace fnr3::port {
namespace {
const ProfileSaveGuestApi original{sub_82391F50,sub_82399900,sub_82295C80,
 sub_82317C98,sub_8228AE78,sub_823192A0,sub_8231A190,sub_8231A338};
RequiredProfileSaveSession pending;
bool Range(uint32_t address,uint32_t length){
 return address>=0x1000&&uint64_t(address)+length<=uint64_t{1}<<32;
}
uint16_t Half(uint8_t* base,uint32_t address){
 return uint16_t(base[address])<<8|base[address+1];
}
bool Text(uint8_t* base,uint32_t address,std::array<char,256>& out){
 if(!Range(address,256))return false;
 const auto* first=reinterpret_cast<const char*>(base+address);
 const auto* end=static_cast<const char*>(std::memchr(first,0,256));
 if(!end||end==first)return false;
 out.fill(0);std::copy(first,end,out.begin());return true;
}
bool ApiValid(const ProfileSaveGuestApi& a){
 return a.argument&&a.to_string&&a.frontend&&a.user_state&&a.manager&&
  a.select_controller&&a.set_name&&a.start_state;
}
bool Scratch(const PPCContext& incoming,PPCContext& work,uint8_t* base){
 // Standard PPC stack frame/linkage area. Original callees grow below this
 // frame; scratch arrays at +128..+895 remain above their stack pointers.
 if(incoming.r1.u64>std::numeric_limits<uint32_t>::max()||
    incoming.r1.u32<0x2000||(incoming.r1.u32&15))return false;
 work=incoming;work.r1.u64=incoming.r1.u32-1024;
 WriteGuestWord(base,work.r1.u32,incoming.r1.u32);return true;
}
bool Snapshot(PPCContext& work,uint8_t* base,const ProfileSaveGuestApi& a,
 ProfileSaveObservation& out,uint32_t& front,uint32_t& user_state){
 a.frontend(work,base);front=work.r3.u32;
 if(!Range(front,1184))return false;
 out.storage=ReadGuestWord(base,front+1160);
 if(!Range(out.storage,6360))return false;
 a.user_state(work,base);user_state=work.r3.u32;
 if(!Range(user_state,3504))return false;
 out.user=static_cast<int32_t>(ReadGuestWord(base,user_state+3356));
 a.manager(work,base);out.manager=work.r3.u32;
 if(!Range(out.manager,536+4*14484))return false;
 out.profile=Half(base,out.manager+360);
 if(out.user<0||out.user>3||out.profile<0||out.profile>3)return false;
 const uint32_t profile=out.manager+536+uint32_t(out.profile)*14484;
 if(!Text(base,profile+14292,out.name))return false;
 out.dirty=ReadGuestWord(base,profile+14316)!=0;
 out.state=static_cast<int32_t>(ReadGuestWord(base,out.storage+4488));
 out.active_state=ReadGuestWord(base,out.storage+4496);
 return true;
}
bool Callback(PPCContext& work,uint8_t* base,const ProfileSaveGuestApi& a,
 uint32_t index,uint32_t scratch,std::array<char,256>& out){
 work.r3.u64=index;a.argument(work,base);const uint32_t value=work.r3.u32;
 if(!Range(value,8))return false;
 const uint32_t flags=ReadGuestWord(base,value+4),type=flags&0x7f;
 if(!(flags&0x08000000)||type<34||type>36)return false;
 // sub_823999D0 cases33..35 stringify only the fixed Function literal
 // (loc_8239A100), so sub_82399900's original unbounded copy is bounded
 // for these accepted types. Arbitrary strings/objects never reach it.
 std::fill_n(base+scratch,256,0);work.r3.u64=value;work.r4.u64=scratch;
 a.to_string(work,base);return Text(base,scratch,out);
}
}
bool StartRequiredProfileSave(PPCContext& incoming,uint8_t* base,
 const ProfileSaveGuestApi& a,RequiredProfileSaveSession& session){
 if(!base||!ApiValid(a)||incoming.r4.u32!=2||!Range(incoming.r3.u32,8)||
    ReadGuestWord(base,a.operand_stack_global)<2)return false;
 PPCContext work{};if(!Scratch(incoming,work,base))return false;
 ProfileSaveObservation owner;uint32_t front=0,user_state=0;
 if(!Snapshot(work,base,a,owner,front,user_state)||owner.state!=-1||owner.active_state||
    !Range(ReadGuestWord(base,owner.storage+4504),4))return false;
 std::array<char,256> success{},failure{};
 const uint32_t scratch=work.r1.u32;
 if(!Callback(work,base,a,0,scratch+384,success)||
    !Callback(work,base,a,1,scratch+640,failure))return false;
 if(!session.Begin(owner))return false;
 // An unchanged Edit can commit without setting this flag. Mark this accepted
 // explicit request dirty so only original successful storage can clear it;
 // cancellation/error remains retryable and cannot report a false success.
 WriteGuestWord(base,owner.manager+536+uint32_t(owner.profile)*14484+14316,1);
 // Same controller and load-slot selections as the original explicit save.
 // SetLoadSlotMC/sub_8231D2D8 stores the validated index at user_state+0.
 work.r3.u64=front;work.r4.s64=owner.user;a.select_controller(work,base);
 WriteGuestWord(base,user_state,uint32_t(owner.profile));
 const uint32_t storage=owner.storage;
 std::copy(success.begin(),success.end(),base+storage+5328);
 std::copy(failure.begin(),failure.end(),base+storage+5584);
 base[storage+6352]=1; // Original asynchronous autosave callback protocol.
 base[storage+6353]=1; // This request is mandatory; preference bit is untouched.
 std::copy(owner.name.begin(),owner.name.end(),base+scratch+128);
 work.r3.u64=storage;work.r4.u64=scratch+128;a.set_name(work,base);
 work.r3.u64=storage;work.r4.u64=1;work.r5.u64=1;a.start_state(work,base);
 return true;
}
ProfileSaveStatus ReadRequiredProfileSaveStatus(PPCContext& incoming,uint8_t* base,
 const ProfileSaveGuestApi& a,const RequiredProfileSaveSession& session){
 if(!base||!ApiValid(a))return ProfileSaveStatus::Invalid;
 PPCContext work{};if(!Scratch(incoming,work,base))return ProfileSaveStatus::Invalid;
 ProfileSaveObservation observation;uint32_t front=0,user_state=0;
 if(!Snapshot(work,base,a,observation,front,user_state))return ProfileSaveStatus::Invalid;
 return session.Observe(observation);
}
bool StartRequiredProfileSave(PPCContext& incoming,uint8_t* base){
 return StartRequiredProfileSave(incoming,base,original,pending);
}
ProfileSaveStatus ReadRequiredProfileSaveStatus(PPCContext& incoming,uint8_t* base){
 return ReadRequiredProfileSaveStatus(incoming,base,original,pending);
}
void ResetRequiredProfileSave(){pending.Reset();}
}
