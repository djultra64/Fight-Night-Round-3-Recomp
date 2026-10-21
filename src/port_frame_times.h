// Optional guest swap cadence tracing. Project work: djultra64.
#pragma once
#include <atomic>
#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <string>
#include <vector>

namespace fnr3::port {
struct FrameTimeSample {
  uint64_t sequence = 0;
  uint64_t steady_ns = 0;
};
struct FrameTimeSnapshot {
  uint64_t total_samples = 0, overwritten_samples = 0, contention_drops = 0;
  std::vector<FrameTimeSample> samples;
};
// Allocates its bounded ring once, before recording. Concurrent producers use a
// single try-lock: an overlapping sample is counted and dropped, never waited on.
class FrameTimeTrace {
public:
  explicit FrameTimeTrace(size_t capacity);
  void RecordNow() noexcept;
  void RecordAt(uint64_t steady_ns) noexcept;  // deterministic contract testing
  FrameTimeSnapshot Snapshot();              // allocating; shutdown/tests only
  size_t capacity() const noexcept { return ring_.size(); }
private:
  bool TryEnter() noexcept;
  void Store(uint64_t steady_ns) noexcept;
  std::vector<FrameTimeSample> ring_;
  uint64_t total_ = 0;
  std::atomic<uint64_t> contention_drops_{0};
  std::atomic_flag writing_ = ATOMIC_FLAG_INIT;
};
struct FrameTimeOptions {
  std::filesystem::path output;  // empty disables tracing (the default)
  std::string cache_state = "unknown";  // cold, warm, unknown
  std::string scene = "unfiltered";
  size_t capacity = 54000;       // 30 minutes at 30 submissions/second
};
// Call only before guest launch. Existing enabled traces must first be flushed.
// Validation/allocation occur here; errors are returned without starting capture.
bool InitializeFrameTimes(const FrameTimeOptions&, std::string* error = nullptr);
void RecordFrameSwap() noexcept;
// Freezes recording and drains active record calls before releasing the ring.
// Safe during shutdown even if a guest hook arrives late. Initialization must
// still happen only before guest launch, with no old guest callers remaining.
// Writes only the explicitly chosen path;
// the directory must already exist. No directory creation or I/O occurs per frame.
bool FlushFrameTimes(std::string* error = nullptr);
}  // namespace fnr3::port
