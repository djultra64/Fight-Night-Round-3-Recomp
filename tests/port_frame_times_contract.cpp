// Guest submission trace contract. Project work: djultra64.
#ifdef NDEBUG
#undef NDEBUG
#endif
#include "port_frame_times.h"
#include <cassert>
#include <sstream>
#include <cstdlib>
#include <new>
#include <thread>
#include <array>

namespace { bool deny_allocations = false; }
void* operator new(std::size_t size) {
  if (deny_allocations) throw std::bad_alloc();
  if (void* value = std::malloc(size ? size : 1)) return value;
  throw std::bad_alloc();
}
void operator delete(void* value) noexcept { std::free(value); }
void operator delete(void* value, std::size_t) noexcept { std::free(value); }
#include <stdexcept>
int main(int argc, char** argv) {
  using namespace fnr3::port;
  FrameTimeTrace trace(3);
  deny_allocations = true;
  trace.RecordAt(100);
  trace.RecordAt(200);
  trace.RecordAt(300);
  trace.RecordAt(400);
  trace.RecordAt(500);
  trace.RecordNow();
  deny_allocations = false;
  auto snapshot = trace.Snapshot();
  assert(snapshot.total_samples == 6 && snapshot.overwritten_samples == 3);
  assert(snapshot.samples.size() == 3);
  assert(snapshot.samples.front().sequence == 3 && snapshot.samples.front().steady_ns == 400);
  assert(snapshot.samples[1].sequence == 4 && snapshot.samples[1].steady_ns == 500);
  bool rejected = false;
  try { FrameTimeTrace invalid(0); } catch (const std::invalid_argument&) { rejected = true; }
  assert(rejected);
  FrameTimeTrace burst(20);
  uint64_t timestamp = 0;
  burst.RecordAt(timestamp);
  for (unsigned i = 0; i < 13; ++i) {
    timestamp += i >= 5 && i < 8 ? 50000000 : 33333333;
    burst.RecordAt(timestamp);
  }
  auto known = burst.Snapshot();
  assert(known.samples.size() == 14 && known.overwritten_samples == 0);
  assert(known.samples[6].steady_ns - known.samples[5].steady_ns == 50000000);
  std::string error;
  assert(InitializeFrameTimes({}, &error));
  RecordFrameSwap();  // off by default
  assert(FlushFrameTimes(&error));
  if (argc > 1) {
    FrameTimeOptions config;
    config.output = argv[1];
    config.cache_state = "cold";
    config.scene = "contract_fixture";
    config.capacity = 2;
    assert(InitializeFrameTimes(config, &error));
    // Reinitialization must not invalidate a published live recorder.
    assert(!InitializeFrameTimes({}, &error));
    deny_allocations = true;
    RecordFrameSwap(); RecordFrameSwap(); RecordFrameSwap();
    deny_allocations = false;
    assert(FlushFrameTimes(&error));
    assert(InitializeFrameTimes({}, &error));
    assert(InitializeFrameTimes(config, &error));
    std::atomic<bool> start{false}, stop{false};
    std::atomic<unsigned> ready{0};
    std::array<std::thread, 4> producers;
    for (auto& producer : producers) producer = std::thread([&] {
      ready.fetch_add(1);
      while (!start.load()) std::this_thread::yield();
      while (!stop.load()) RecordFrameSwap();
      // These late calls must be harmless after the ring has been freed.
      for (unsigned i = 0; i < 1000; ++i) RecordFrameSwap();
    });
    while (ready.load() != producers.size()) std::this_thread::yield();
    start.store(true);
    for (unsigned i = 0; i < 1000; ++i) RecordFrameSwap();
    assert(FlushFrameTimes(&error));  // guest producers deliberately still live
    stop.store(true);
    for (auto& producer : producers) producer.join();
    assert(InitializeFrameTimes({}, &error));
  }
}
