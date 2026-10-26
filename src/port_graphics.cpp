// Unified port settings, separate from guest simulation. Work: djultra64.
#include "port_graphics.h"
#include <rex/cvar.h>
#include <rex/logging.h>
REXCVAR_DEFINE_STRING(fnr3_resolution, "720p", "Port/Video", "Resolution")
    .allowed({"720p", "900p", "1080p", "1440p", "1800p", "2160p"})
    .lifecycle(rex::cvar::Lifecycle::kRequiresRestart);
REXCVAR_DEFINE_STRING(fnr3_fxaa, "none", "Port/Video", "FXAA")
    .allowed({"none", "fxaa", "fxaa_extreme"})
    .lifecycle(rex::cvar::Lifecycle::kRequiresRestart);
REXCVAR_DEFINE_STRING(fnr3_texture_filter, "4x", "Port/Video",
                      "Texture filtering")
    .allowed({"original", "1x", "2x", "4x", "8x", "16x"})
    .lifecycle(rex::cvar::Lifecycle::kRequiresRestart);
REXCVAR_DEFINE_BOOL(fnr3_fullscreen, false, "Port/Video", "Fullscreen")
    .lifecycle(rex::cvar::Lifecycle::kRequiresRestart);
REXCVAR_DEFINE_STRING(fnr3_frame_rate, "60", "Port/Video", "Frame rate")
    .allowed({"30", "60"})
    .lifecycle(rex::cvar::Lifecycle::kRequiresRestart);
namespace fnr3::port {
void ApplyGraphicsSettings() {
  const GraphicsSettings settings{REXCVAR_GET(fnr3_resolution),
                                  REXCVAR_GET(fnr3_fxaa),
                                  REXCVAR_GET(fnr3_texture_filter),
                                  REXCVAR_GET(fnr3_fullscreen),
                                  REXCVAR_GET(fnr3_frame_rate)=="30"?30u:60u};
  auto flags = GraphicsFlags(settings);
  if(rex::cvar::GetFlagByName("fnr3_texture_bake_readback_abi")!="1")
    throw std::runtime_error("Missing selective texture bake readback capability");
  const auto runtime_flags = StableRuntimeFlags();
  flags.insert(flags.end(),runtime_flags.begin(),runtime_flags.end());
  // Preflight before changing anything. An incompatible SDK must not silently
  // start with only half of a resolution/presentation preset applied.
  for (const auto &[name, value] : flags)
    if (!rex::cvar::GetFlagInfo(name))
      throw std::runtime_error("Missing port graphics capability: " + name);
  for (const auto &[name, value] : flags)
    if (!rex::cvar::SetFlagByName(name, value))
      throw std::runtime_error("Rejected port graphics setting: " + name);
  REXLOG_INFO("FNR3: physical window {}x{}, internal scale {}x{}, complete draws {}, blocking preload {}",
              rex::cvar::GetFlagByName("window_width"), rex::cvar::GetFlagByName("window_height"),
              rex::cvar::GetFlagByName("draw_resolution_scale_x"), rex::cvar::GetFlagByName("draw_resolution_scale_y"),
              rex::cvar::GetFlagByName("vulkan_complete_draws"), rex::cvar::GetFlagByName("shader_preload_blocking"));
  const FlagList keyboard_defaults={{"keybind_a","Space"},{"keybind_b","Backspace"},
    {"keybind_start","Return"},{"keybind_dpad_up","Up"},{"keybind_dpad_down","Down"},
    {"keybind_dpad_left","Left"},{"keybind_dpad_right","Right"}};
  for(const auto& [name,value]:keyboard_defaults)
    if(rex::cvar::GetFlagSource(name)==rex::cvar::Source::kDefault)
      if(!rex::cvar::SetFlagByName(name,value))throw std::runtime_error("Missing keyboard input capability: "+name);
  REXLOG_INFO("FNR3: graphics settings, resolution {}, FXAA {}, filtering {}, gameplay {} FPS",
              settings.resolution, settings.post_effect,
              settings.texture_filter,settings.frame_rate);
}
} // namespace fnr3::port
