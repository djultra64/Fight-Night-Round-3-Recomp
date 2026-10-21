// Real SDK configuration check: no device, window, runtime or title launch.
// Project work: djultra64.
#ifdef NDEBUG
#undef NDEBUG
#endif
#include "port_graphics.h"
#include <cassert>
#include <iostream>
#include <rex/cvar.h>
#include <rex/system/gpu_plugin.h>
int main(int argc, char **argv) {
  rex::cvar::Init(argc, argv);
  auto gpu = rex::system::LoadGpuPlugin("xenos", "vulkan");
  assert(gpu);
  // Loading registers the plugin's flags and constructs an inert graphics
  // system. Device/presentation creation belongs to the uncalled Setup methods.
  assert(!gpu->provider() && !gpu->presenter() && !gpu->has_presentation());
  const auto keyboard_source = rex::cvar::GetFlagSource("keybind_a");
  const auto keyboard_value = rex::cvar::GetFlagByName("keybind_a");
  const auto dpad_source = rex::cvar::GetFlagSource("keybind_dpad_up");
  const auto dpad_value = rex::cvar::GetFlagByName("keybind_dpad_up");
  fnr3::port::ApplyGraphicsSettings();
  assert(!gpu->provider() && !gpu->presenter() && !gpu->has_presentation());
  assert(rex::cvar::GetFlagByName("keybind_a") ==
      (keyboard_source == rex::cvar::Source::kDefault ? "Space" : keyboard_value));
  assert(rex::cvar::GetFlagByName("keybind_dpad_up") ==
      (dpad_source == rex::cvar::Source::kDefault ? "Up" : dpad_value));
  if (keyboard_source != rex::cvar::Source::kDefault)
    assert(rex::cvar::GetFlagSource("keybind_a") == keyboard_source);
  std::cout << "keyboard A before source=" << unsigned(keyboard_source)
            << " value=" << keyboard_value << "; after=" << rex::cvar::GetFlagByName("keybind_a")
            << "; D-pad up before source=" << unsigned(dpad_source)
            << " value=" << dpad_value << "; after=" << rex::cvar::GetFlagByName("keybind_dpad_up") << "\n";
  assert(rex::cvar::GetFlagByName("draw_resolution_scale_x") == "3");
  assert(rex::cvar::GetFlagByName("window_width") == "3840");
  assert(rex::cvar::GetFlagByName("swap_post_effect") == "fxaa");
  assert(rex::cvar::GetFlagByName("anisotropic_override") == "5");
  assert(rex::cvar::GetFlagByName("store_shaders") == "true");
  assert(rex::cvar::GetFlagByName("fnr3_audio_frame_pacing") == "true");
  assert(rex::cvar::GetFlagByName("fnr3_xma_no_lookahead") == "true");
  assert(rex::cvar::GetFlagByName("fnr3_xmp_no_delay") == "false");
  assert(rex::cvar::GetFlagByName("fnr3_direct_resolve") == "false");
  assert(rex::cvar::GetFlagByName("input_backend") == "sdl");
  assert(rex::cvar::GetFlagByName("mnk_mode") == "true");
  assert(!rex::cvar::GetFlagInfo("fnr3_60fps"));
  assert(!rex::cvar::GetFlagInfo("fnr3_visual_interpolation"));
  std::cout << "PASS real SDK port profile, native plugin flags, no "
               "experimental clocks\n";
}
