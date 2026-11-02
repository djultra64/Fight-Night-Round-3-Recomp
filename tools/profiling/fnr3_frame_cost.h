// Optional CPU-side Vulkan cost capture. Project work: djultra64.
// Included ONLY inside rexgpu-xenos, never in the host EXE/runtime DLL.
#pragma once
#include <atomic>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <filesystem>
#include <memory>
#include <stdexcept>
#include <string_view>
#include <vector>
#if defined(_WIN32)
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#endif

namespace rex::graphics::vulkan::fnr3_cost {
inline constexpr uint32_t kMaxCapacity = 1048576;
enum class Stage : uint32_t {
  kBeginSubmission, kEndSubmission, kFenceCheck, kFenceWait, kFencePoll,
  kFenceObserved, kDeferredExecute, kQueueAcquire, kQueueSubmit,
  kConfigurePipeline, kRequiredPipelineWait, kDrainPipelineWait
};
inline std::string_view StageName(Stage stage) noexcept {
  constexpr std::string_view names[] = {
      "begin_submission_cpu", "end_submission_cpu", "fence_check_cpu",
      "fence_wait_cpu", "fence_poll_cpu", "fence_observed_cpu",
      "deferred_execute_cpu", "queue_acquire_cpu", "queue_submit_cpu",
      "configure_pipeline_cpu", "required_pipeline_wait_cpu", "drain_pipeline_wait_cpu"};
  return names[static_cast<uint32_t>(stage)];
}
inline uint64_t NowNs() noexcept {
  return uint64_t(std::chrono::duration_cast<std::chrono::nanoseconds>(
      std::chrono::steady_clock::now().time_since_epoch()).count());
}
inline bool ThreadCpuNs(uint64_t& value) noexcept {
#if defined(_WIN32)
  FILETIME created, exited, kernel, user;
  if (!GetThreadTimes(GetCurrentThread(), &created, &exited, &kernel, &user)) return false;
  value = (((uint64_t(kernel.dwHighDateTime) << 32) | kernel.dwLowDateTime) +
           ((uint64_t(user.dwHighDateTime) << 32) | user.dwLowDateTime)) * 100;
  return true;
#else
  return false;
#endif
}
struct Event {
  uint64_t sequence = 0, submission_id = 0, backend_frame_id = 0;
  uint64_t start_ns = 0, end_ns = 0, cpu_ns = 0, items = 0;
  uint32_t thread_id = 0;
  Stage stage{};
  int32_t result = 0;
  bool cpu_available = false, result_available = false;
};
struct Snapshot {
  std::vector<Event> events;
  uint64_t total = 0, overwritten = 0, contention_drops = 0, pending_scopes = 0, shutdown_drops = 0;
  bool lock_acquired = false;
  bool Complete() const noexcept {
    return lock_acquired && total && !overwritten && !contention_drops && !pending_scopes && !shutdown_drops;
  }
};
class Recorder {
 public:
  explicit Recorder(uint32_t capacity, bool thread_cpu) : thread_cpu_(thread_cpu) {
    if (!capacity || capacity > kMaxCapacity) throw std::invalid_argument("frame cost capacity");
    ring_.resize(capacity);
  }
  bool Enter() noexcept {
    if (!enabled_.load()) return false;
    pending_.fetch_add(1);
    if (!enabled_.load()) { pending_.fetch_sub(1); return false; }
    return true;
  }
  void Leave(Event event) noexcept {
    // No spinning, heap allocation, logging or I/O on the producer path.
    if (writing_.test_and_set(std::memory_order_acquire)) {
      contention_drops_.fetch_add(1);
    } else {
      if (enabled_.load()) {
        event.sequence = total_;
        ring_[total_ % ring_.size()] = event;
        ++total_;
      } else {
        shutdown_drops_.fetch_add(1);
      }
      writing_.clear(std::memory_order_release);
    }
    pending_.fetch_sub(1);
  }
  void Disable() noexcept { enabled_.store(false); }
  Snapshot Stop() {
    // Never wait for a GPU/pipeline scope, or a producer that may be suspended
    // during shutdown. The recorder must outlive every outstanding Scope.
    Disable();
    Snapshot snapshot;
    snapshot.pending_scopes = pending_.load();
    snapshot.contention_drops = contention_drops_.load();
    snapshot.shutdown_drops = shutdown_drops_.load();
    if (writing_.test_and_set(std::memory_order_acquire)) return snapshot;
    struct Unlock {
      std::atomic_flag& flag;
      ~Unlock() { flag.clear(std::memory_order_release); }
    } unlock{writing_};
    snapshot.lock_acquired = true;
    snapshot.total = total_;
    snapshot.overwritten = total_ > ring_.size() ? total_ - ring_.size() : 0;
    snapshot.events.reserve(size_t(total_ - snapshot.overwritten));
    for (uint64_t i = snapshot.overwritten; i != total_; ++i)
      snapshot.events.push_back(ring_[i % ring_.size()]);
    return snapshot;
  }
  bool thread_cpu() const noexcept { return thread_cpu_; }
 private:
  friend struct RecorderTestAccess;
  const bool thread_cpu_;
  std::vector<Event> ring_;
  std::atomic<bool> enabled_{true};
  std::atomic<uint64_t> pending_{0}, contention_drops_{0}, shutdown_drops_{0};
  std::atomic_flag writing_ = ATOMIC_FLAG_INIT;
  uint64_t total_ = 0;
};
// State belongs to the plugin module. Start publishes exactly once and never
// frees it: _Exit skips destructors, and late worker scopes may still hold it.
inline std::atomic<Recorder*> active{nullptr};
class Scope {
 public:
  Scope(Stage stage, uint64_t submission_id, uint64_t backend_frame_id) noexcept {
    recorder_ = active.load(std::memory_order_acquire);
    if (!recorder_ || !recorder_->Enter()) { recorder_ = nullptr; return; }
    event_.stage = stage;
    event_.submission_id = submission_id;
    event_.backend_frame_id = backend_frame_id;
#if defined(_WIN32)
    event_.thread_id = GetCurrentThreadId();
#endif
    cpu_started_ = recorder_->thread_cpu() && ThreadCpuNs(cpu_start_);
    event_.start_ns = NowNs();
  }
  Scope(const Scope&) = delete;
  Scope& operator=(const Scope&) = delete;
  ~Scope() { Finish(); }
  void Result(int32_t result) noexcept { event_.result = result; event_.result_available = true; }
  void Items(uint64_t items) noexcept { event_.items = items; }
  void Finish() noexcept {
    if (!recorder_) return;
    event_.end_ns = NowNs();
    uint64_t cpu_end;
    event_.cpu_available = cpu_started_ && ThreadCpuNs(cpu_end) && cpu_end >= cpu_start_;
    if (event_.cpu_available) event_.cpu_ns = cpu_end - cpu_start_;
    recorder_->Leave(event_);
    recorder_ = nullptr;
  }
 private:
  Recorder* recorder_ = nullptr;
  Event event_{};
  uint64_t cpu_start_ = 0;
  bool cpu_started_ = false;
};

enum class FailureCause : uint32_t { kNone, kQueueSubmitDeviceLost, kFenceDeviceLost };
inline const char* FailureJson(FailureCause cause) noexcept {
  switch (cause) {
    case FailureCause::kQueueSubmitDeviceLost: return "\"vkQueueSubmit_device_lost\"";
    case FailureCause::kFenceDeviceLost: return "\"vkWaitForFences_device_lost\"";
    default: return "null";
  }
}

#if defined(_WIN32)
// This transport is called through C exports in plugin_main.cpp. Setup and
// normal shutdown run on the UI thread. A fatal Vulkan path may also request
// export; exactly one caller wins without waiting for another exporter.
inline HANDLE output_file = INVALID_HANDLE_VALUE;
inline Recorder* owned_recorder = nullptr;
inline bool capture_attempted = false;
inline std::atomic_flag export_claimed = ATOMIC_FLAG_INIT;
inline std::atomic<FailureCause> failure_cause{FailureCause::kNone};
inline bool Write(std::string_view text) noexcept {
  DWORD written = 0;
  return WriteFile(output_file, text.data(), DWORD(text.size()), &written, nullptr) &&
         written == text.size();
}
// Status: 0 success, 1 invalid/unavailable/setup failure, 2 incomplete, 3 I/O failure.
inline uint32_t Start(const wchar_t* path, uint32_t capacity, uint32_t thread_cpu) noexcept {
  if (capture_attempted) return 1;  // One capture per process; no lifetime reuse.
  capture_attempted = true;
  try {
    if (!path || !*path || !std::filesystem::path(path).is_absolute() || thread_cpu > 1) return 1;
    auto recorder = std::make_unique<Recorder>(capacity, thread_cpu != 0);
    // Never truncate a previous run. Require an existing directory and a new file.
    output_file = CreateFileW(path, GENERIC_WRITE, FILE_SHARE_READ, nullptr, CREATE_NEW,
                              FILE_ATTRIBUTE_NORMAL, nullptr);
    if (output_file == INVALID_HANDLE_VALUE) return 1;
    char metadata[1024];
    const int n = std::snprintf(metadata, sizeof(metadata),
        "{\"type\":\"capture_start\",\"schema_version\":1,\"source\":\"vulkan_cpu_submission_partial\","
        "\"author\":\"djultra64\",\"clock_domain\":\"cpu_steady_clock\",\"units\":\"ns\","
        "\"frame_id_mapping\":null,\"gpu_timestamps\":null,\"presentation\":null,"
        "\"coverage\":\"selected_cpu_scopes\",\"capture_complete\":false,\"capacity\":%u,"
        "\"thread_cpu_requested\":%s}\n", capacity, thread_cpu ? "true" : "false");
    if (n < 0 || size_t(n) >= sizeof(metadata) || !Write({metadata, size_t(n)}) ||
        !FlushFileBuffers(output_file)) {
      CloseHandle(output_file); output_file = INVALID_HANDLE_VALUE; return 3;
    }
    owned_recorder = recorder.release();
    active.store(owned_recorder, std::memory_order_release);
    return 0;
  } catch (...) { return 1; }
}
inline uint32_t StopAndExport(FailureCause cause = FailureCause::kNone) noexcept {
  // Acquire publication before reading initialization state. No handle/recorder
  // accesses on a competing export path, even if the winner is closing it.
  if (!active.load(std::memory_order_acquire)) return 1;
  if (cause != FailureCause::kNone) {
    auto expected = FailureCause::kNone;
    failure_cause.compare_exchange_strong(expected, cause);
  }
  if (export_claimed.test_and_set(std::memory_order_acquire)) return 2;
  // Disable first; retained allocation makes already-entered scopes safe.
  // Do not clear active: stopped scopes see enabled=false without touching clocks.
  owned_recorder->Disable();
  uint32_t result = 3;
  try {
    char line[1024];
    bool ok = true;
    // Persist the actual failure before allocating/copying the snapshot. Even
    // a contended ring or snapshot allocation failure must preserve the cause.
    const auto initial_cause = failure_cause.load();
    if (initial_cause != FailureCause::kNone) {
      const int n = std::snprintf(line, sizeof(line),
          "{\"type\":\"capture_failure\",\"reason\":%s,\"vk_result\":-4,\"capture_complete\":false}\n",
          FailureJson(initial_cause));
      if (n < 0 || size_t(n) >= sizeof(line) || !Write({line, size_t(n)}) || !FlushFileBuffers(output_file)) {
        // Retain an incomplete file; never emit a successful footer after an
        // I/O failure that may have left a partial JSON line.
        ok = false;
      }
    }
    const auto snapshot = owned_recorder->Stop();
    for (const auto& e : snapshot.events) {
      char cpu[32] = "null", status[32] = "null", submission[32] = "null", frame[32] = "null";
      if (e.cpu_available) std::snprintf(cpu, sizeof(cpu), "%llu", (unsigned long long)e.cpu_ns);
      if (e.result_available) std::snprintf(status, sizeof(status), "%d", e.result);
      if (e.submission_id) std::snprintf(submission, sizeof(submission), "%llu", (unsigned long long)e.submission_id);
      if (e.backend_frame_id) std::snprintf(frame, sizeof(frame), "%llu", (unsigned long long)e.backend_frame_id);
      const int n = std::snprintf(line, sizeof(line),
          "{\"type\":\"event\",\"sequence\":%llu,\"frame_id\":null,\"backend_frame_id\":%s,"
          "\"submission_id\":%s,\"stage\":\"%s\",\"clock_domain\":\"cpu_steady_clock\","
          "\"timestamp_ns\":%llu,\"duration_ns\":%llu,\"thread_id\":%u,\"thread_cpu_ns\":%s,"
          "\"result\":%s,\"items\":%llu,\"status\":\"scope_returned\"}\n",
          (unsigned long long)e.sequence, frame, submission, StageName(e.stage).data(),
          (unsigned long long)e.start_ns, (unsigned long long)(e.end_ns - e.start_ns),
          e.thread_id, cpu, status, (unsigned long long)e.items);
      if (n < 0 || size_t(n) >= sizeof(line) || !Write({line, size_t(n)})) { ok = false; break; }
    }
    char total[32] = "null", overwritten[32] = "null";
    if (snapshot.lock_acquired) {
      std::snprintf(total, sizeof(total), "%llu", (unsigned long long)snapshot.total);
      std::snprintf(overwritten, sizeof(overwritten), "%llu", (unsigned long long)snapshot.overwritten);
    }
    const auto final_cause = failure_cause.load();
    const bool complete = snapshot.Complete() && final_cause == FailureCause::kNone;
    const int n = std::snprintf(line, sizeof(line),
        "{\"type\":\"capture_end\",\"schema_version\":1,\"capture_complete\":%s,"
        "\"snapshot_available\":%s,\"total_events\":%s,\"retained_events\":%llu,"
        "\"overwritten_events\":%s,\"contention_drops\":%llu,\"pending_scopes\":%llu,\"shutdown_drops\":%llu,"
        "\"thread_cpu_requested\":%s,\"thread_cpu_clock\":\"GetThreadTimes_100ns\",\"failure_reason\":%s}\n",
        complete ? "true" : "false", snapshot.lock_acquired ? "true" : "false",
        total, (unsigned long long)snapshot.events.size(), overwritten,
        (unsigned long long)snapshot.contention_drops, (unsigned long long)snapshot.pending_scopes,
        (unsigned long long)snapshot.shutdown_drops, owned_recorder->thread_cpu() ? "true" : "false",
        FailureJson(final_cause));
    if (ok && n >= 0 && size_t(n) < sizeof(line) && Write({line, size_t(n)}) && FlushFileBuffers(output_file))
      result = complete ? 0 : 2;
  } catch (...) {
    // Allocation failure during snapshot cannot touch or free a live producer.
    Write("{\"type\":\"capture_error\",\"capture_complete\":false,\"reason\":\"export_failed\"}\n");
  }
  if (!CloseHandle(output_file)) result = 3;
  output_file = INVALID_HANDLE_VALUE;
  return result;
}
#endif
inline void RescueDeviceLoss(FailureCause cause) noexcept {
#if defined(_WIN32)
  // Called only after a real VK_ERROR_DEVICE_LOST, immediately before the
  // existing fatal handler. Never waits for GPU, queues, scopes or exporters.
  (void)StopAndExport(cause);
#else
  (void)cause;
#endif
}
}  // namespace rex::graphics::vulkan::fnr3_cost
