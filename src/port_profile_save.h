// Required custom boxer profile persistence. Project work: djultra64.
#pragma once
#include <array>
#include <cstdint>
#include <cstring>
struct PPCContext;
namespace fnr3::port {
enum class ProfileSaveStatus : int { Invalid=0, Pending=1, Success=2, Failed=3 };
struct ProfileSaveObservation {
 uint32_t storage=0,manager=0;
 int32_t user=-1,profile=-1,state=-1;
 uint32_t active_state=0;
 bool dirty=false;
 std::array<char,256> name{};
};
// Portable policy: success requires original storage completion and unchanged
// owner/profile/name. The optional autosave preference never authorizes skipping.
class RequiredProfileSaveSession {
 ProfileSaveObservation owner_{};
 bool active_=false;
 static bool Valid(const ProfileSaveObservation& s){
  return s.storage&&s.manager&&s.user>=0&&s.user<4&&s.profile>=0&&s.profile<4&&
   s.name[0]&&std::memchr(s.name.data(),0,s.name.size());
 }
public:
 bool Begin(const ProfileSaveObservation& s){
  if(!Valid(s)||s.state!=-1||s.active_state)return false;
  owner_=s;active_=true;return true;
 }
 ProfileSaveStatus Observe(const ProfileSaveObservation& s)const{
  if(!active_||!Valid(s)||s.storage!=owner_.storage||s.manager!=owner_.manager||
     s.user!=owner_.user||s.profile!=owner_.profile||s.name!=owner_.name)
   return ProfileSaveStatus::Invalid;
  if(s.state!=-1||s.active_state)return ProfileSaveStatus::Pending;
  return s.dirty?ProfileSaveStatus::Failed:ProfileSaveStatus::Success;
 }
 void Reset(){active_=false;}
};
using ProfileSaveGuestFunction=void(PPCContext&,uint8_t*);
// Dependency boundary for the original guest API, also used by the contract.
struct ProfileSaveGuestApi {
 ProfileSaveGuestFunction *argument,*to_string,*frontend,*user_state,*manager,
  *select_controller,*set_name,*start_state;
 uint32_t operand_stack_global=0x8284C8D8;
};
// Both entry points preserve the incoming PPC context. Start takes exactly the
// original two APT callback arguments; caller supplies the GC-managed result.
bool StartRequiredProfileSave(PPCContext&,uint8_t*);
ProfileSaveStatus ReadRequiredProfileSaveStatus(PPCContext&,uint8_t*);
void ResetRequiredProfileSave();
bool StartRequiredProfileSave(PPCContext&,uint8_t*,const ProfileSaveGuestApi&,
 RequiredProfileSaveSession&);
ProfileSaveStatus ReadRequiredProfileSaveStatus(PPCContext&,uint8_t*,
 const ProfileSaveGuestApi&,const RequiredProfileSaveSession&);
}
