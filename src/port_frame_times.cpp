// Optional guest swap cadence tracing. Project work: djultra64.
#include "port_frame_times.h"
#include <chrono>
#include <fstream>
#include <memory>
#include <stdexcept>
#include <thread>
#include <utility>

namespace fnr3::port {
namespace {
uint64_t NowNs() noexcept {
  return static_cast<uint64_t>(std::chrono::duration_cast<std::chrono::nanoseconds>(
      std::chrono::steady_clock::now().time_since_epoch()).count());
}
std::unique_ptr<FrameTimeTrace> trace;
std::atomic<FrameTimeTrace*> active{nullptr};
std::atomic<bool> recording_enabled{false};
std::atomic<uint64_t> in_flight{0};
FrameTimeOptions options;
uint64_t origin_ns = 0;
void SetError(std::string* error, const std::string& value) {
  if (error) *error = value;
}
std::string JsonString(const std::string& value) {
  constexpr char hex[] = "0123456789abcdef";
  std::string result = "\"";
  for (unsigned char ch : value) {
    if (ch == '"' || ch == '\\') { result += '\\'; result += ch; }
    else if (ch < 0x20) {
      result += "\\u00"; result += hex[ch >> 4]; result += hex[ch & 15];
    } else result += ch;
  }
  return result + '"';
}
}  // namespace

FrameTimeTrace::FrameTimeTrace(size_t capacity) {
  // Bound user-controlled allocation independently of the producer path.
  if (capacity == 0 || capacity > 10000000)
    throw std::invalid_argument("frame trace capacity must be 1..10000000");
  ring_.resize(capacity);
}
bool FrameTimeTrace::TryEnter() noexcept {
  if (writing_.test_and_set(std::memory_order_acquire)) {
    contention_drops_.fetch_add(1, std::memory_order_relaxed);
    return false;
  }
  return true;
}
void FrameTimeTrace::Store(uint64_t steady_ns) noexcept {
  ring_[total_ % ring_.size()] = {total_, steady_ns};
  ++total_;
  writing_.clear(std::memory_order_release);
}
void FrameTimeTrace::RecordNow() noexcept {
  if (TryEnter()) Store(NowNs());
}
void FrameTimeTrace::RecordAt(uint64_t steady_ns) noexcept {
  if (TryEnter()) Store(steady_ns);
}
FrameTimeSnapshot FrameTimeTrace::Snapshot() {
  while (writing_.test_and_set(std::memory_order_acquire)) std::this_thread::yield();
  // Release the flag even if allocation fails; a failed export can be retried.
  struct Unlock { std::atomic_flag& flag; ~Unlock() { flag.clear(std::memory_order_release); } } unlock{writing_};
  FrameTimeSnapshot snapshot;
  snapshot.total_samples = total_;
  snapshot.overwritten_samples = total_ > ring_.size() ? total_ - ring_.size() : 0;
  snapshot.contention_drops = contention_drops_.load(std::memory_order_relaxed);
  const auto retained = static_cast<size_t>(total_ - snapshot.overwritten_samples);
  snapshot.samples.reserve(retained);
  for (uint64_t seq = snapshot.overwritten_samples; seq < total_; ++seq)
    snapshot.samples.push_back(ring_[seq % ring_.size()]);
  return snapshot;
}
bool InitializeFrameTimes(const FrameTimeOptions& config, std::string* error) {
  SetError(error, "");
  if (trace) {
    SetError(error, "frame trace must be flushed before reinitialization");
    return false;
  }
  if (config.output.empty()) return true;
  if (config.cache_state != "cold" && config.cache_state != "warm" && config.cache_state != "unknown") {
    SetError(error, "frame trace cache_state must be cold, warm or unknown");
    return false;
  }
  try {
    // Copy options and allocate before publishing the pointer to guest threads.
    options = config;
    auto recorder = std::make_unique<FrameTimeTrace>(config.capacity);
    origin_ns = NowNs();
    trace = std::move(recorder);
    active.store(trace.get(), std::memory_order_release);
    recording_enabled.store(true);
    return true;
  } catch (const std::exception& exception) {
    SetError(error, exception.what());
    return false;
  }
}
void RecordFrameSwap() noexcept {
  if (!recording_enabled.load()) return;
  // Increment before the second enabled check. A late caller that observed
  // enabled before Flush but increments after the drain cannot access the
  // recorder, because that second check observes the disabled state. Sequential
  // consistency orders these checks/counter operations against Flush's drain.
  in_flight.fetch_add(1);
  if (recording_enabled.load())
    if (auto* recorder = active.load(std::memory_order_acquire)) recorder->RecordNow();
  in_flight.fetch_sub(1);
}
bool FlushFrameTimes(std::string* error) {
  SetError(error, "");
  recording_enabled.store(false);
  while (in_flight.load() != 0) std::this_thread::yield();
  active.store(nullptr, std::memory_order_release);
  if (!trace) return true;
  try {
    const auto snapshot = trace->Snapshot();
    std::ofstream output(options.output, std::ios::out | std::ios::trunc);
    if (!output) throw std::runtime_error("cannot open frame trace output path");
    output << "{\"type\":\"metadata\",\"schema_version\":1,"
              "\"author\":\"djultra64\",\"source\":\"guest_swap_routine_entry\","
              "\"clock\":\"steady_clock\",\"cache_state\":" << JsonString(options.cache_state)
           << ",\"scene\":" << JsonString(options.scene)
           << ",\"origin_ns\":" << origin_ns << ",\"capacity\":" << trace->capacity()
           << ",\"total_samples\":" << snapshot.total_samples
           << ",\"retained_samples\":" << snapshot.samples.size()
           << ",\"overwritten_samples\":" << snapshot.overwritten_samples
           << ",\"contention_drops\":" << snapshot.contention_drops << "}\n";
    for (const auto& sample : snapshot.samples)
      output << "{\"type\":\"sample\",\"sequence\":" << sample.sequence
             << ",\"steady_ns\":" << sample.steady_ns << "}\n";
    output.flush();
    if (!output) throw std::runtime_error("failed writing frame trace output");
    trace.reset();
    options = {};
    return true;
  } catch (const std::exception& exception) {
    // Retain the stopped ring for retry; never silently discard failed output.
    SetError(error, exception.what());
    return false;
  }
}
}  // namespace fnr3::port

#ifndef FNR3_FRAME_TIMES_NO_GUEST_HOOK
#include <rex/ppc/context.h>
// This original routine unconditionally calls VdSwap once (guest 0x82388228).
// Its entry records submission cadence, not GPU completion or presentation time.
extern "C" void __imp__sub_82388048(PPCContext&, uint8_t*);
extern "C" void sub_82388048(PPCContext& ctx, uint8_t* base) {
  fnr3::port::RecordFrameSwap();
  __imp__sub_82388048(ctx, base);
}
#endif
