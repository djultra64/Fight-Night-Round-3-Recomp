// Native gameplay/replay phase policies. Project work: djultra64.
#pragma once
#include <cstdint>
namespace fnr3::port::timing {
struct PhaseClock { uint32_t object, rate, phases; };
struct PhaseGate { uint32_t mode, scene, state; };
struct PhaseBackup { bool applied = false; PhaseClock previous{}; };
inline void RestoreOriginalPhase(PhaseBackup& saved, PhaseClock& clock) noexcept {
  if (!saved.applied) return;
  if (clock.object == saved.previous.object &&
      (clock.rate == 60 || clock.rate == saved.previous.rate) && clock.phases == 0)
    clock = saved.previous;
  saved.applied = false;
}
inline bool ApplyNativePhase(PhaseBackup& saved, PhaseClock& clock, bool enabled,
                             PhaseGate expected, PhaseGate actual) noexcept {
  if (!enabled || expected.mode != actual.mode || expected.scene != actual.scene ||
      expected.state != actual.state || clock.rate != 30 || clock.phases != 1) return false;
  saved.previous = clock; saved.applied = true;
  clock.rate = 60; clock.phases = 0;
  return true;
}
inline bool ApplyReplayPhase(PhaseBackup& saved, PhaseClock& clock, bool enabled,
                             bool replay, PhaseGate expected, PhaseGate actual) noexcept {
  if (!enabled || !replay || actual.mode != expected.mode || actual.scene != expected.scene ||
      actual.state != 1 || (clock.rate != 20 && clock.rate != 30) || clock.phases != 1) return false;
  saved.previous = clock; saved.applied = true;
  clock.rate = 60; clock.phases = 0;
  return true;
}
struct ReplayCountdown {
  uint32_t object = 0, remaining = 0;
  float fraction = 0;
  uint32_t Advance(uint32_t obj, uint32_t current, float scale) noexcept {
    if (obj != object || current != remaining || scale == 1.f) { object = obj; fraction = 0; }
    fraction += scale;
    const auto count = uint32_t(fraction + 1e-6f);
    fraction -= count;
    remaining = current > count ? current - count : 0;
    return remaining;
  }
};
struct ReplayStepClock {
  uint64_t previous = 0;
  bool valid = false;
  void Reset() noexcept { valid = false; }
  float Step(uint64_t now, uint32_t original_callbacks) noexcept {
    const float initial = float(original_callbacks) / 60.f;
    if (!valid) { previous = now; valid = true; return initial; }
    const uint64_t elapsed = now > previous ? now - previous : 0;
    previous = now;
    // Pauses, debugger stops and discontinuities are not replay time.
    if (!elapsed || elapsed > 250000000ull) return initial;
    return float(double(elapsed) * 1e-9 * original_callbacks);
  }
};
struct CrowdAdvance { uint32_t samples = 2; float remainder = 0; };
inline CrowdAdvance AdvanceCrowd(double elapsed_samples) noexcept {
  CrowdAdvance advance;
  if (elapsed_samples >= .999 && elapsed_samples < 1000000.) {
    advance.samples = uint32_t(elapsed_samples + .001);
    advance.remainder = float(elapsed_samples - double(advance.samples));
    if (advance.remainder < 0) advance.remainder = 0;
  }
  return advance;
}
} // namespace fnr3::port::timing
