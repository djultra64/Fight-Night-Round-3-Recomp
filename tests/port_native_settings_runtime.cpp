// Actual SDK settings registry and native session; no window/title/device.
// Project work: djultra64.
#include "port_native_graphics.h"
#include "port_settings_runtime.h"
#include <rex/cvar.h>
#include <rex/ppc/context.h>
#include <rex/system/gpu_plugin.h>
#include <algorithm>
#include <cstdlib>
#include <iostream>
#include <map>
extern "C" void __imp__sub_8251AA38(PPCContext&,uint8_t*) {}
namespace {
void check(bool condition,const char* message) {
  if(!condition){std::cerr<<message<<'\n';std::exit(1);}
}
}
int main(int argc,char** argv) {
  using namespace fnr3::port;
  rex::cvar::Init(argc,argv);
  auto gpu=rex::system::LoadGpuPlugin("xenos","vulkan");
  check(bool(gpu),"Actual SDK GPU plugin registers backend settings");
  check(!gpu->provider()&&!gpu->presenter()&&!gpu->has_presentation(),"No graphics device or window initialized");
  rex::cvar::FinalizeInit();
  ActionBindings custom;
  custom.Bind(InputAction::Confirm,PhysicalButton::East);
  custom.Bind(InputAction::Pause,PhysicalButton::North);
  for(unsigned i=0;i<kActionCount;++i)BindAction(InputAction(i),custom.physical[i]);
  const auto initial=ReadCurrentPortSettings();
  check(initial.bindings.physical==custom.physical,"Nondefault 14-action permutation initialized");
  std::map<std::string,std::string> backend;
  for(const char* name:{"vsync","resolution_scale","draw_resolution_scale_x","draw_resolution_scale_y","swap_post_effect","anisotropic_override"}) {
    check(bool(rex::cvar::GetFlagInfo(name)),"Actual backend flag exists");
    backend[name]=rex::cvar::GetFlagByName(name);
  }
  for(const char* name:{"fnr3_resolution","fnr3_fxaa","fnr3_texture_filter","fnr3_fullscreen"})
    check(rex::cvar::GetFlagInfo(name)->lifecycle==rex::cvar::Lifecycle::kRequiresRestart,"Graphics profile is restart-only");
  rex::cvar::ClearPendingRestartFlags();
  NativeGraphicsSession session;
  session.Begin(initial);
  for(int field=0;field<5;++field)session.Step(field,1);
  const auto wanted=session.Pending();
  const auto root=std::filesystem::temp_directory_path()/("fnr3-native-settings-"+std::to_string(std::chrono::steady_clock::now().time_since_epoch().count()));
  const auto path=root/"port-settings.toml";
  session.Save([&](const PortSettings& value){PersistPortSettings(path,value);});
  check(std::filesystem::is_regular_file(path),"Native Save created user settings");
  const auto reread=ReadCurrentPortSettings();
  check(SerializePortSettings(reread)==SerializePortSettings(wanted),"Save updates desired SDK values read by next native session");
  check(reread.bindings.physical==custom.physical,"Save preserves all 14 existing bindings");
  NativeGraphicsSession reopened;
  reopened.Begin(reread);
  for(int field=0;field<5;++field)check(reopened.Get(field)==session.Get(field),"Reopen keeps saved finite selection");
  const auto pending=rex::cvar::GetPendingRestartFlags();
  for(const char* name:{"fnr3_resolution","fnr3_fxaa","fnr3_texture_filter","fnr3_fullscreen"})
    check(std::find(pending.begin(),pending.end(),name)!=pending.end(),"Restart requirement retained after Save");
  for(const auto& [name,value]:backend)check(rex::cvar::GetFlagByName(name)==value,"Native Save must not mutate live backend values");
  reopened.Step(0,1);reopened.Cancel();
  check(SerializePortSettings(ReadCurrentPortSettings())==SerializePortSettings(wanted),"Cancel leaves persisted/live requested values unchanged");
  const auto blocker=root/"not-a-directory";{std::ofstream file(blocker);file<<"block";}
  session.Step(0,1);bool failed=false;
  try{session.Save([&](const PortSettings& value){PersistPortSettings(blocker/"settings.toml",value);});}
  catch(const std::filesystem::filesystem_error&){failed=true;}
  check(failed,"Persistence failure is reported");
  check(SerializePortSettings(ReadCurrentPortSettings())==SerializePortSettings(wanted),"Failed save cannot change SDK desired values or bindings");
  check(!gpu->provider()&&!gpu->presenter()&&!gpu->has_presentation(),"Contract remained headless");
  std::filesystem::remove_all(root);
  std::cout<<"PASS real SDK native settings Save/read/reopen, restart lifecycle, backend immutability, 14 bindings, cancel and failure\n";
}
