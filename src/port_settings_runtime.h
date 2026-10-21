// Shared persistence for native menus and control remapping. Work: djultra64.
#pragma once
#include "port_settings.h"
#include <rex/cvar.h>
namespace fnr3::port {
inline InputFamily SettingsInputFamily(const std::string& f){return f=="xbox"?InputFamily::Xbox:f=="playstation"?InputFamily::PlayStation:f=="switch"?InputFamily::Switch:InputFamily::Automatic;}
inline PortSettings ReadCurrentPortSettings(){
 PortSettings s;
 s.graphics={rex::cvar::GetFlagByName("fnr3_resolution"),rex::cvar::GetFlagByName("fnr3_fxaa"),rex::cvar::GetFlagByName("fnr3_texture_filter"),rex::cvar::GetFlagByName("fnr3_fullscreen")=="true"};
 auto f=SelectedInputFamily();s.input_family=f==InputFamily::Xbox?"xbox":f==InputFamily::PlayStation?"playstation":f==InputFamily::Switch?"switch":"auto";
 s.bindings=GetActionBindings();(void)SerializePortSettings(s);return s;
}
inline void PersistPortSettings(const std::filesystem::path& path,const PortSettings& s){
 (void)SerializePortSettings(s);
 for(const char* name:{"fnr3_resolution","fnr3_fxaa","fnr3_texture_filter","fnr3_fullscreen","fnr3_input_family","fnr3_action_bindings"})
  if(!rex::cvar::GetFlagInfo(name))throw std::runtime_error(std::string("Missing port setting: ")+name);
 SavePortSettingsFile(path,s);
 for(const auto& setting:std::array<std::pair<std::string,std::string>,4>{{{"fnr3_resolution",s.graphics.resolution},{"fnr3_fxaa",s.graphics.post_effect},{"fnr3_texture_filter",s.graphics.texture_filter},{"fnr3_fullscreen",s.graphics.fullscreen?"true":"false"}}})
  if(!rex::cvar::SetFlagByName(setting.first,setting.second))throw std::runtime_error("Setting rejected: "+setting.first);
 SelectInputFamily(SettingsInputFamily(s.input_family));
 for(unsigned i=0;i<kActionCount;++i)BindAction(InputAction(i),s.bindings.physical[i]);
 SuppressHeldInputButtons();
}
} // namespace fnr3::port
