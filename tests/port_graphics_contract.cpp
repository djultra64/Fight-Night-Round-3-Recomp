// Port graphics policy regression. Project work: djultra64.
#ifdef NDEBUG
#undef NDEBUG
#endif
#include "port_graphics.h"
#include <cassert>
#include <iostream>
#include <map>
using namespace fnr3::port;
int main() {
  auto runtime = StableRuntimeFlags();
  std::map<std::string,std::string> required(runtime.begin(),runtime.end());
  assert(required.at("fnr3_audio_frame_pacing")=="true");
  assert(required.at("fnr3_xma_no_lookahead")=="true");
  assert(required.at("fnr3_xmp_no_delay")=="false");
  assert(required.at("input_backend")=="sdl");
  assert(required.at("mnk_mode")=="true");
  auto defaults = GraphicsFlags({});
  std::map<std::string, std::string> flags(defaults.begin(), defaults.end());
  assert(flags.at("window_width") == "1280");
  assert(flags.contains("fnr3_native60_beta") && flags.at("fnr3_native60_beta")=="true");
  GraphicsSettings thirty;thirty.frame_rate=30;auto f30=GraphicsFlags(thirty);
  std::map<std::string,std::string> map30(f30.begin(),f30.end());
  assert(map30.at("fnr3_native60_beta")=="false");
  thirty.frame_rate=120;bool invalid_rate=false;try{(void)GraphicsFlags(thirty);}catch(const std::invalid_argument&){invalid_rate=true;}assert(invalid_rate);
  assert(flags.at("fullscreen") == "false");
  assert(flags.at("draw_resolution_scale_x") == "1");
  assert(flags.at("vulkan_allow_present_mode_immediate") == "false");
  assert(flags.at("store_shaders") == "true");
  assert(!flags.contains("fnr3_60fps") &&
         !flags.contains("fnr3_visual_interpolation"));
  auto high = GraphicsFlags({"2160p", "fxaa", "16x", true});
  flags = {high.begin(), high.end()};
  assert(flags.at("window_width") == "3840" &&
         flags.at("window_height") == "2160");
  assert(flags.at("draw_resolution_scale_x") == "3" &&
         flags.at("draw_resolution_scale_y") == "3");
  // The SDK takes an enumeration, not the anisotropy multiplier.
  assert(flags.at("anisotropic_override") == "5");
  assert(flags.at("swap_post_effect") == "fxaa");
  assert(flags.at("fullscreen") == "true");
  for (const auto &resolution : Resolutions()) {
    const auto &p = resolution;
    assert(p.width * 9 == p.height * 16);
    assert(p.scale * 1280 >= p.width && p.scale * 720 >= p.height);
  }
  unsigned rejected = 0;
  for (auto bad : {GraphicsSettings{"1080p;quit", "none", "4x"},
                   GraphicsSettings{"720p", "taa", "4x"},
                   GraphicsSettings{"720p", "none", "64x"}}) {
    try {
      (void)GraphicsFlags(bad);
    } catch (const std::invalid_argument &) {
      ++rejected;
    }
  }
  assert(rejected == 3);
  std::cout << "PASS unified resolution, bounded quality, SDK enum mapping and "
               "original-rate policy\n";
}
