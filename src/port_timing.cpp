// Portable native gameplay and recorded-replay timing. Project work: djultra64.
#include "port_timing.h"
#include <rex/cvar.h>
#include <cerrno>
#include <chrono>
REXCVAR_DEFINE_BOOL(fnr3_native60_beta, true, "FNR3",
    "Native 60 Hz gameplay and time-correct recorded replays")
    .lifecycle(rex::cvar::Lifecycle::kRequiresRestart);
namespace {
using namespace fnr3::port::timing;
// Guest phase/sequence hooks run on the guest scheduling thread.
PhaseBackup phase_backup;
bool replay_sequence = false;
ReplayCountdown replay_countdown;
ReplayStepClock replay_clock;
uint32_t GuestWord(const uint8_t* base, uint32_t addr) noexcept {
  const auto* p = base + addr;
  return uint32_t(p[0]) << 24 | uint32_t(p[1]) << 16 | uint32_t(p[2]) << 8 | p[3];
}
void GuestWord(uint8_t* base, uint32_t addr, uint32_t value) noexcept {
  auto* p = base + addr;
  p[0] = uint8_t(value >> 24); p[1] = uint8_t(value >> 16);
  p[2] = uint8_t(value >> 8); p[3] = uint8_t(value);
}
PhaseClock ReadPhaseClock(const uint8_t* base) noexcept {
  const auto object = GuestWord(base, 0x8295D030);
  return {object, object ? GuestWord(base, object + 484) : 0, GuestWord(base, 0x827C4508)};
}
void WritePhaseClock(uint8_t* base, PhaseClock clock) noexcept {
  GuestWord(base, clock.object + 484, clock.rate);
  GuestWord(base, 0x827C4508, clock.phases);
}
bool ReadPhaseGate(const uint8_t* base, PhaseGate& gate) noexcept {
  const auto manager = GuestWord(base, 0x8283FDBC), modes = GuestWord(base, 0x82842B48);
  if (!manager || !modes) return false;
  const auto scene = GuestWord(base, manager + 16);
  if (!scene) return false;
  gate = {GuestWord(base, modes + 76), scene, GuestWord(base, scene + 56)};
  return true;
}
} // namespace
extern "C" void Fnr3Native60Begin(uint8_t* base) noexcept {
  if (!phase_backup.applied) return;
  auto clock = ReadPhaseClock(base);
  const auto before = clock;
  RestoreOriginalPhase(phase_backup, clock);
  if (clock.rate != before.rate || clock.phases != before.phases) WritePhaseClock(base, clock);
}
extern "C" void Fnr3Native60End(uint8_t* base) noexcept {
  if (!REXCVAR_GET(fnr3_native60_beta)) return;
  PhaseGate actual{};
  if (!ReadPhaseGate(base, actual)) return;
  auto clock = ReadPhaseClock(base);
  if (clock.object && ApplyNativePhase(phase_backup, clock, true, {1, actual.scene, 0}, actual))
    WritePhaseClock(base, clock);
}
extern "C" void Fnr3ReplaySequenceBegin(uint8_t* base, uint32_t parent) noexcept {
  const auto event = GuestWord(base, parent + 112);
  replay_clock.Reset();
  replay_sequence = event == 8 || event == 9 || event == 10 || event == 13;
}
extern "C" void Fnr3ReplaySequenceEnd(uint8_t* base) noexcept {
  if (replay_sequence) Fnr3Native60Begin(base);
  replay_sequence = false; replay_countdown = {}; replay_clock.Reset();
}
extern "C" void Fnr3ReplayPhaseEnd(uint8_t* base) noexcept {
  if (!replay_sequence || !REXCVAR_GET(fnr3_native60_beta)) { replay_clock.Reset(); return; }
  PhaseGate actual{};
  if (!ReadPhaseGate(base, actual)) return;
  auto clock = ReadPhaseClock(base);
  if (clock.object && GuestWord(base, 0x82842B24) &&
      ApplyReplayPhase(phase_backup, clock, true, true, {1, actual.scene, 1}, actual))
    WritePhaseClock(base, clock);
  else replay_clock.Reset();
}
extern "C" float Fnr3ReplayTickScale(uint8_t*) noexcept {
  if (!replay_sequence || !phase_backup.applied) { replay_clock.Reset(); return 1.f; }
  const int saved_errno = errno;
  const auto now = std::chrono::steady_clock::now();
  errno = saved_errno;
  const auto ns = std::chrono::duration_cast<std::chrono::nanoseconds>(now.time_since_epoch()).count();
  return replay_clock.Step(static_cast<uint64_t>(ns), phase_backup.previous.rate * 2);
}
extern "C" uint32_t Fnr3ReplayCountdown(uint32_t object, uint32_t current, float scale) noexcept {
  return replay_countdown.Advance(object, current, scale);
}
