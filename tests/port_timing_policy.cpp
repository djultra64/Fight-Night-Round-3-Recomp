// Portable scheduler regression tests. Project work: djultra64.
// Run with assertions enabled (no NDEBUG).
#include "port_timing_policy.h"
#include <cmath>
#include <initializer_list>
#include <cstdio>
#include <cstdlib>
using namespace fnr3::port::timing;
#define CHECK(expr) do { if (!(expr)) { std::fprintf(stderr, "line %d: %s\n", __LINE__, #expr); std::abort(); } } while (false)
int main() {
  const PhaseGate fight{1, 0x1000, 0}, replay{1, 0x1000, 1};
  PhaseBackup saved;
  PhaseClock clock{0x2000, 30, 1};
  CHECK(!ApplyNativePhase(saved, clock, false, fight, fight));
  for (auto actual : {PhaseGate{0,0x1000,0}, PhaseGate{1,0x3000,0}, replay})
    CHECK(!ApplyNativePhase(saved, clock, true, fight, actual));
  CHECK(ApplyNativePhase(saved, clock, true, fight, fight));
  CHECK(clock.rate == 60 && clock.phases == 0 && saved.applied);
  RestoreOriginalPhase(saved, clock);
  CHECK(clock.rate == 30 && clock.phases == 1 && !saved.applied);
  CHECK(ApplyNativePhase(saved, clock, true, fight, fight));
  clock.object = 0x3000; RestoreOriginalPhase(saved, clock);
  CHECK(clock.object == 0x3000 && clock.rate == 60 && !saved.applied);
  for (auto rate : {20u,30u}) {
    clock = {0x2000, rate, 1};
    CHECK(ApplyReplayPhase(saved, clock, true, true, replay, replay));
    RestoreOriginalPhase(saved, clock); CHECK(clock.rate == rate && clock.phases == 1);
  }
  clock = {0x2000,20,1};
  CHECK(!ApplyNativePhase(saved, clock, true, fight, fight));
  CHECK(!ApplyReplayPhase(saved, clock, true, false, replay, replay));
  CHECK(!ApplyReplayPhase(saved, clock, true, true, replay, fight));
  clock = {0x2000,60,1}; CHECK(!ApplyReplayPhase(saved, clock, true, true, replay, replay));
  ReplayStepClock step;
  CHECK(step.Step(1000000000,40) == 40.f/60.f);
  CHECK(std::abs(step.Step(1025000000,40) - 1.f) < 1e-6f);
  CHECK(step.Step(2000000000,40) == 40.f/60.f); // pause is not replay time
  CHECK(step.Step(1000000000,40) == 40.f/60.f); // clock discontinuity
  step.Reset(); CHECK(step.Step(3000000000,60) == 1.f);
  ReplayCountdown countdown;
  uint32_t remaining=100;
  for(int n=0;n<60;++n) remaining=countdown.Advance(1,remaining,40.f/60.f);
  CHECK(remaining == 60);
  CHECK(countdown.Advance(2,50,0.5f) == 50); // new object resets fraction
  CHECK(countdown.Advance(2,50,0.5f) == 49);
  CHECK(countdown.Advance(2,20,0.5f) == 20); // external countdown change resets
  CHECK(countdown.Advance(2,20,1.f) == 19);
  CHECK(countdown.Advance(2,1,5.f) == 0); // saturate
  auto crowd = AdvanceCrowd(1.5); CHECK(crowd.samples == 1 && crowd.remainder == .5f);
  crowd = AdvanceCrowd(2.0); CHECK(crowd.samples == 2 && crowd.remainder == 0);
  crowd = AdvanceCrowd(.9995); CHECK(crowd.samples == 1 && crowd.remainder == 0);
  crowd = AdvanceCrowd(1000000); CHECK(crowd.samples == 2 && crowd.remainder == 0);
}
