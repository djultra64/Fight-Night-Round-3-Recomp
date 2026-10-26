// Original-rate resolution port policy. Project work: djultra64.
#pragma once
#include <array>
#include <stdexcept>
#include <string>
#include <string_view>
#include <utility>
#include <vector>
namespace fnr3::port {
struct Resolution {
  std::string_view id;
  unsigned width, height, scale;
};
inline constexpr auto Resolutions() {
  // The pinned Xenos SDK supports integer render scales. Intermediate display
  // sizes use the next integer render size and downsample; no fractional GPU
  // scale is claimed. The product presents one resolution setting.
  return std::array{
      Resolution{"720p", 1280, 720, 1},   Resolution{"900p", 1600, 900, 2},
      Resolution{"1080p", 1920, 1080, 2}, Resolution{"1440p", 2560, 1440, 2},
      Resolution{"1800p", 3200, 1800, 3}, Resolution{"2160p", 3840, 2160, 3}};
}
struct GraphicsSettings {
  std::string resolution = "720p", post_effect = "none", texture_filter = "4x";
  bool fullscreen = false;
  unsigned frame_rate = 60;
};
using FlagList = std::vector<std::pair<std::string, std::string>>;
inline FlagList GraphicsFlags(const GraphicsSettings &settings) {
  if(settings.frame_rate!=30 && settings.frame_rate!=60)
    throw std::invalid_argument("Unsupported port frame rate");
  const Resolution *selected = nullptr;
  const auto resolutions = Resolutions();
  for (const auto &p : resolutions)
    if (p.id == settings.resolution)
      selected = &p;
  if (!selected)
    throw std::invalid_argument("Unsupported port resolution");
  if (settings.post_effect != "none" && settings.post_effect != "fxaa" &&
      settings.post_effect != "fxaa_extreme")
    throw std::invalid_argument("Unsupported port post effect");
  constexpr std::array<std::pair<std::string_view, int>, 6> filters = {
      {{"original", -1},
       {"1x", 1},
       {"2x", 2},
       {"4x", 3},
       {"8x", 4},
       {"16x", 5}}};
  int filter = -2;
  for (const auto &[name, value] : filters)
    if (name == settings.texture_filter)
      filter = value;
  if (filter == -2)
    throw std::invalid_argument("Unsupported port texture filter");
  return {{"fnr3_native60_beta", settings.frame_rate==60?"true":"false"},
          {"fullscreen", settings.fullscreen ? "true" : "false"},
          {"resolution_scale", std::to_string(selected->scale)},
          {"draw_resolution_scale_x", std::to_string(selected->scale)},
          {"draw_resolution_scale_y", std::to_string(selected->scale)},
          {"window_width", std::to_string(selected->width)},
          {"window_height", std::to_string(selected->height)},
          {"window_size_in_pixels", "true"},
    {"vulkan_complete_draws", "true"},
    {"shader_preload_blocking", "false"},
          {"swap_post_effect", settings.post_effect},
          {"anisotropic_override", std::to_string(filter)},
          {"store_shaders", "true"},
          {"vsync", "true"},
          {"vulkan_allow_present_mode_mailbox", "true"},
          {"vulkan_allow_present_mode_immediate", "false"},
          {"vulkan_allow_present_mode_fifo_relaxed", "false"}};
}
// Preserve the accepted audio/input runtime behavior in standalone packages;
// these repaired SDK switches default off for other games.
inline FlagList StableRuntimeFlags() {
  return {{"fnr3_audio_frame_pacing","true"},
          {"fnr3_xma_no_lookahead","true"},
          {"fnr3_xmp_no_delay","false"},
          {"fnr3_direct_resolve","false"},
          {"input_backend","sdl"}, {"mnk_mode","true"}};
}
// Called after GPU plugin registration, before creating its device/caches.
void ApplyGraphicsSettings();
} // namespace fnr3::port
