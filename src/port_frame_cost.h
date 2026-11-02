// Host control for optional plugin-owned CPU tracing. Work: djultra64.
#pragma once
#include <rex/logging.h>
#include <cstdint>
#include <cstdlib>
#include <cwchar>
#include <filesystem>
#include <string_view>
#if defined(_WIN32)
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#endif

namespace fnr3::port {
#if defined(_WIN32)
using StopFrameCostFn = uint32_t (*)() noexcept;
inline StopFrameCostFn stop_frame_cost = nullptr;
inline void InitializeFrameCost() noexcept {
  const wchar_t* output = _wgetenv(L"FNR3_FRAME_COST");
  if (!output || !*output || stop_frame_cost) return;
  try {
    uint32_t capacity = 262144;
    if (const wchar_t* value = _wgetenv(L"FNR3_FRAME_COST_CAPACITY")) {
      wchar_t* end = nullptr;
      const auto parsed = std::wcstoull(value, &end, 10);
      if (value == end || *end || !parsed || parsed > 1048576 || *value == L'-') {
        REXLOG_WARN("FNR3: CPU cost capture unavailable: invalid capacity (1..1048576)");
        return;
      }
      capacity = uint32_t(parsed);
    }
    uint32_t cpu = 0;
    if (const wchar_t* value = _wgetenv(L"FNR3_FRAME_COST_THREAD_CPU")) {
      if (std::wstring_view(value) == L"1") cpu = 1;
      else if (std::wstring_view(value) != L"0") {
        REXLOG_WARN("FNR3: CPU cost capture unavailable: thread CPU option must be 0 or 1");
        return;
      }
    }
    wchar_t executable[32768];
    const DWORD length = GetModuleFileNameW(nullptr, executable, 32768);
    if (!length || length >= 32768) {
      REXLOG_WARN("FNR3: CPU cost capture unavailable: executable path lookup failed");
      return;
    }
    // Resolve only the already-loaded plugin beside this executable. Do not
    // load another DLL or instantiate a recorder in the executable/runtime.
    const auto path = std::filesystem::path(executable).parent_path() / L"rexgpu-xenos.dll";
    const HMODULE plugin = GetModuleHandleW(path.c_str());
    using StartFn = uint32_t (*)(const wchar_t*, uint32_t, uint32_t) noexcept;
    const auto start = plugin ? reinterpret_cast<StartFn>(GetProcAddress(plugin, "Fnr3FrameCostStartV1")) : nullptr;
    const auto stop = plugin ? reinterpret_cast<StopFrameCostFn>(GetProcAddress(plugin, "Fnr3FrameCostStopV1")) : nullptr;
    if (!start || !stop) {
      REXLOG_WARN("FNR3: CPU cost capture unavailable: loaded plugin lacks diagnostics ABI V1");
      return;
    }
    const uint32_t status = start(output, capacity, cpu);
    if (status) {
      REXLOG_WARN("FNR3: CPU cost capture unavailable (status {}); use a new absolute output path", status);
      return;
    }
    stop_frame_cost = stop;
    REXLOG_INFO("FNR3: partial Vulkan CPU cost capture enabled, capacity {}, thread CPU {}", capacity, cpu);
  } catch (...) {
    REXLOG_WARN("FNR3: optional CPU cost capture setup failed");
  }
}
inline void FlushFrameCost() noexcept {
  const auto stop = stop_frame_cost;
  if (!stop) return;
  stop_frame_cost = nullptr;
  const uint32_t status = stop();
  if (status == 0) REXLOG_INFO("FNR3: partial Vulkan CPU cost trace exported");
  else REXLOG_WARN("FNR3: Vulkan CPU cost trace incomplete or unavailable (status {})", status);
}
#else
inline void InitializeFrameCost() noexcept {}
inline void FlushFrameCost() noexcept {}
#endif
}  // namespace fnr3::port
