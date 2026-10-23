// Native APT host callbacks. Project work: djultra64.
#include "port_menu.h"
#include "port_apt.h"
#include "port_native_graphics.h"
#include "port_settings_runtime.h"
#include <mutex>
#include <atomic>
#include <cstring>
#include <rex/logging.h>
#include <rex/cvar.h>
#include <rex/runtime.h>
#include <rex/system/function_dispatcher.h>
#include <rex/system/xmemory.h>
extern "C" {
void __imp__sub_823086F0(PPCContext&,uint8_t*);
void sub_823986D0(PPCContext&,uint8_t*);
void __imp__sub_8238E658(PPCContext&,uint8_t*);
void sub_8239E680(PPCContext&,uint8_t*);
void __imp__sub_82391FA8(PPCContext&,uint8_t*);
void sub_82391F50(PPCContext&,uint8_t*);
void sub_82399388(PPCContext&,uint8_t*);
void sub_823A2D28(PPCContext&,uint8_t*);
}
namespace fnr3::port {
namespace {
std::atomic<std::shared_ptr<MenuQueue>> dispatch;
std::atomic<bool> registered{false};
uint32_t quit_thunk=0,graphics_thunk=0,name_address=0;
void NativeQuit(PPCContext& ctx,uint8_t* base){
 if(auto q=dispatch.load())q->Request(MenuAction::Quit);
 __imp__sub_82391FA8(ctx,base);
}
std::mutex settings_mutex;
NativeGraphicsSession settings_session;
std::filesystem::path settings_path;
const AptValueApi value_api{sub_82391F50,sub_82399388,sub_823A2D28};
void NativeGraphics(PPCContext& ctx,uint8_t* base){
 // Retained ABI only. Graphics navigation is now entirely inside the movie.
 __imp__sub_82391FA8(ctx,base);
}
void NativeEvent(PPCContext& ctx,uint8_t* base){
 int result=0;
 try{
  auto command=ReadAptIntegerArgument(ctx,base,value_api);
  if(command){
   std::lock_guard lock(settings_mutex);const int event=*command;
   if(event==0){settings_session.Begin(ReadCurrentPortSettings());SuppressHeldInputButtons();result=1;}
   else if(event==1){settings_session.Cancel();result=1;}
   else if(event==3){settings_session.Save([](const PortSettings& s){PersistPortSettings(settings_path,s);});if(auto q=dispatch.load())result=q->Request(MenuAction::Restart)?1:0;}
   else if(event==2){settings_session.Save([](const PortSettings& s){PersistPortSettings(settings_path,s);});result=1;}
   else if(event>=10&&event<16){settings_session.Step(event-10,-1);result=1;}
   else if(event>=20&&event<26){settings_session.Step(event-20,1);result=1;}
   else if(event>=100&&event<114){settings_session.StepBinding(event-100,-1);result=1;}
   else if(event>=200&&event<214){settings_session.StepBinding(event-200,1);result=1;}
   else if(event==300){settings_session.ResetBindings();result=1;}
  }
 }catch(const std::exception& e){REXLOG_ERROR("FNR3: native graphics action failed: {}",e.what());}
 MakeAptIntegerResult(ctx,base,result,value_api);
}
template<int Field> void NativeGet(PPCContext& ctx,uint8_t* base){
 int result=-1;
 try{std::lock_guard lock(settings_mutex);result=settings_session.Get(Field);}
 catch(const std::exception& e){REXLOG_ERROR("FNR3: native graphics read failed: {}",e.what());}
 MakeAptIntegerResult(ctx,base,result,value_api);
}
void NativeBinding(PPCContext& ctx,uint8_t* base){
 int result=-1;
 try{auto action=ReadAptIntegerArgument(ctx,base,value_api);if(action){std::lock_guard lock(settings_mutex);result=settings_session.GetBinding(*action);}}
 catch(const std::exception& e){REXLOG_ERROR("FNR3: native binding read failed: {}",e.what());}
 MakeAptIntegerResult(ctx,base,result,value_api);
}
void NativeActiveFamily(PPCContext& ctx,uint8_t* base){
 int result=1;
 {std::lock_guard lock(settings_mutex);
  if(settings_session.Active())result=settings_session.Get(4);
  if(result==0){const auto f=DetectedInputFamily();result=f==InputFamily::PlayStation?2:f==InputFamily::Switch?3:1;}}
 MakeAptIntegerResult(ctx,base,result,value_api);
}
struct NativeMethod {const char* name;PPCFunc* function;uint32_t thunk=0,address=0;};
std::array<NativeMethod,9> methods={{{"PortGraphicsEvent",NativeEvent},{"PortGetResolution",NativeGet<0>},{"PortGetFullscreen",NativeGet<1>},{"PortGetFxaa",NativeGet<2>},{"PortGetFiltering",NativeGet<3>},{"PortGetFamily",NativeGet<4>},{"PortGetFrameRate",NativeGet<5>},{"PortGetBinding",NativeBinding},{"PortGetActiveFamily",NativeActiveFamily}}};
}
void InitializePortMenus(rex::Runtime& runtime,std::shared_ptr<MenuQueue> queue,const std::filesystem::path& path){
 if(!queue)throw std::runtime_error("Missing UI menu queue");
 auto* dispatcher=runtime.function_dispatcher();
 quit_thunk=dispatcher->AllocateThunk(NativeQuit,0);
 graphics_thunk=dispatcher->AllocateThunk(NativeGraphics,0);
 name_address=runtime.memory()->SystemHeapAlloc(sizeof("PortGraphics"));
 if(!quit_thunk||!graphics_thunk||!name_address)throw std::runtime_error("Cannot allocate native menu callbacks");
 std::memcpy(runtime.virtual_membase()+name_address,"PortGraphics",sizeof("PortGraphics"));
 for(auto& method:methods){
  method.thunk=dispatcher->AllocateThunk(method.function,0);
  method.address=runtime.memory()->SystemHeapAlloc(std::strlen(method.name)+1);
  if(!method.thunk||!method.address)throw std::runtime_error("Cannot allocate native graphics service");
  std::memcpy(runtime.virtual_membase()+method.address,method.name,std::strlen(method.name)+1);
 }
 {std::lock_guard lock(settings_mutex);settings_path=path;settings_session.Cancel();}
 registered.store(false);dispatch.store(std::move(queue));
}
void ShutdownPortMenus(){if(auto q=dispatch.exchange(nullptr))q->Shutdown();}
bool PortMenuCallbacksRegistered(){return registered.load();}
void RegisterPortMenus(PPCContext& ctx,uint8_t* base,uint32_t root){
 if(!dispatch.load())return;
 try {
  BindAptHostActions(ctx,base,root,{sub_823986D0,__imp__sub_8238E658,sub_8239E680},quit_thunk,graphics_thunk,name_address);
  const AptApi api{sub_823986D0,__imp__sub_8238E658,sub_8239E680};
  for(const auto& method:methods)RegisterAptHostMethod(ctx,base,root,api,method.thunk,method.address);
  registered.store(true);
  REXLOG_INFO("FNR3: native Quit and Graphics callbacks registered");
 }catch(const std::exception& e){
  REXLOG_ERROR("FNR3: native menu registration failed: {}",e.what());
  if(auto q=dispatch.load())q->Request(MenuAction::Quit);
 }
}
}
extern "C" void sub_823086F0(PPCContext& ctx,uint8_t* base){
 const auto root=ctx.r3.u32;
 __imp__sub_823086F0(ctx,base);
 fnr3::port::RegisterPortMenus(ctx,base,root);
}

REXCVAR_DEFINE_STRING(fnr3_frontend_root,"","Port/Resources","Prepared local menu overrides").lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_STRING(fnr3_glyph_root,"","Port/Resources","Prepared local controller glyphs").lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_STRING(fnr3_frame_trace,"","Port/Diagnostics","Optional frame cadence output path").lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_STRING(fnr3_trace_cache,"unknown","Port/Diagnostics","Trace shader cache state").allowed({"unknown","cold","warm"}).lifecycle(rex::cvar::Lifecycle::kInitOnly);
REXCVAR_DEFINE_STRING(fnr3_trace_scene,"unfiltered","Port/Diagnostics","Trace scene annotation").lifecycle(rex::cvar::Lifecycle::kInitOnly);
