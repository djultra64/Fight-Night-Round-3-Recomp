// Explicit port-only persistence. Project work: djultra64.
#pragma once
#include "port_graphics.h"
#include "port_input.h"
#include <chrono>
#include <filesystem>
#include <fstream>
#include <system_error>
#if defined(_WIN32)
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#endif
namespace fnr3::port {
struct PortSettings {
  GraphicsSettings graphics;
  std::string input_family="auto";
  ActionBindings bindings;
};
inline std::string SerializePortSettings(const PortSettings& s) {
  (void)GraphicsFlags(s.graphics);
  if(s.input_family!="auto"&&s.input_family!="xbox"&&s.input_family!="playstation"&&s.input_family!="switch")
    throw std::invalid_argument("Invalid input family");
  unsigned seen=0;std::string mapping;
  for(auto p:s.bindings.physical){auto v=unsigned(p);if(v>=kActionCount||(seen&(1u<<v)))throw std::invalid_argument("Invalid action mapping");seen|=1u<<v;if(!mapping.empty())mapping+=',';mapping+=std::to_string(v);}
  return "# Fight Night Round 3 port settings. Work: djultra64.\n"
    "fnr3_resolution = \""+s.graphics.resolution+"\"\n"
    "fnr3_fxaa = \""+s.graphics.post_effect+"\"\n"
    "fnr3_texture_filter = \""+s.graphics.texture_filter+"\"\n"
    "fnr3_fullscreen = "+(s.graphics.fullscreen?"true":"false")+"\n"
    "fnr3_frame_rate = \""+std::to_string(s.graphics.frame_rate)+"\"\n"
    "fnr3_input_family = \""+s.input_family+"\"\n"
    "fnr3_action_bindings = \""+mapping+"\"\n";
}
inline void SavePortSettingsFile(const std::filesystem::path& path,const PortSettings& settings) {
  const auto content=SerializePortSettings(settings); // Validate before creating anything.
  if(path.empty())throw std::invalid_argument("Missing settings destination");
  if(!path.parent_path().empty())std::filesystem::create_directories(path.parent_path());
  static std::atomic<uint64_t> nonce{0};
  auto temporary=path;temporary+=".tmp."+std::to_string(std::chrono::steady_clock::now().time_since_epoch().count())+"."+std::to_string(nonce++);
  try {
    {std::ofstream output(temporary,std::ios::binary|std::ios::trunc);if(!output)throw std::runtime_error("Cannot create settings file");output<<content;output.flush();if(!output)throw std::runtime_error("Cannot write settings file");output.close();if(!output)throw std::runtime_error("Cannot close settings file");}
#if defined(_WIN32)
    if(!MoveFileExW(temporary.c_str(),path.c_str(),MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH))
      throw std::system_error(int(GetLastError()),std::system_category(),"Cannot replace settings file");
#else
    std::filesystem::rename(temporary,path);
#endif
  }catch(...){std::error_code ignored;std::filesystem::remove(temporary,ignored);throw;}
}
} // namespace fnr3::port
