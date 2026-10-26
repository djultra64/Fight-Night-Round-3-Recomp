"""Compile actual SDK lookup/worker methods against a controllable driver boundary.

Work: djultra64. Run with SDK_ROOT and redirect stdout to a C++23 source file.
"""
from pathlib import Path
import sys


def extract(text, signature):
    start = text.index(signature)
    brace = text.index('{', start)
    end, depth = brace + 1, 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]


def generate(sdk):
    source = (sdk / 'src/graphics/vulkan/pipeline_cache.cpp').read_text()
    lookup = extract(source, 'void VulkanPipelineCache::GetPipelineAndLayoutByHandle(')
    return PREFIX + lookup + SUFFIX


PREFIX = r'''
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cstdint>
#include <cstdlib>
#include <future>
#include <iostream>
#include <mutex>
#include <thread>
using namespace std::chrono_literals;
using VkPipeline = uintptr_t;
constexpr VkPipeline VK_NULL_HANDLE = 0;
bool cfg_vulkan_complete_draws = true;
#define REXCVAR_GET(x) cfg_##x
#define REXGPU_INFO(...) do {} while (0)
struct VulkanPipelineCache {
 struct PipelineLayoutProvider { int id; };
 enum class CreationStatus { kEmpty, kPending, kReady, kFailed };
 struct Pipeline {
   std::atomic<VkPipeline> pipeline{0};
   std::atomic<const PipelineLayoutProvider*> pipeline_layout{nullptr};
   std::atomic<bool> is_placeholder{false};
   std::atomic<CreationStatus> creation_status{CreationStatus::kEmpty};
 };
 mutable std::atomic<uint64_t> pipeline_wait_count_{0}, pipeline_wait_microseconds_{0};
 void GetPipelineAndLayoutByHandle(void*, VkPipeline&, const PipelineLayoutProvider*&, bool*) const;
};
void require(bool b, const char* message) { if (!b) { std::cerr << message << '\n'; std::exit(1); } }
'''
SUFFIX = r'''
int main() {
 using Status = VulkanPipelineCache::CreationStatus;
 using Pipeline = VulkanPipelineCache::Pipeline;
 using Layout = VulkanPipelineCache::PipelineLayoutProvider;
 VulkanPipelineCache c;
 Layout provisional{1}, real{2};
 Pipeline p;
 p.pipeline = 11; p.pipeline_layout = &provisional; p.is_placeholder = true;
 p.creation_status = Status::kPending;
 auto draw = std::async(std::launch::async, [&] {
   VkPipeline handle = 0; const Layout* layout = nullptr; bool placeholder = true;
   c.GetPipelineAndLayoutByHandle(&p, handle, layout, &placeholder);
   return handle == 22 && layout == &real && !placeholder;
 });
 require(draw.wait_for(40ms) == std::future_status::timeout,
         "draw was discarded or used an unfinished pipeline instead of waiting");
 p.pipeline = 22;
 // Deliberately separate the stores: observing a new handle is not completion.
 require(draw.wait_for(20ms) == std::future_status::timeout, "mixed pipeline/layout publication");
 p.pipeline_layout = &real; p.is_placeholder = false;
 p.creation_status.store(Status::kReady, std::memory_order_release);
 p.creation_status.notify_all();
 require(draw.wait_for(1s) == std::future_status::ready && draw.get(), "completed draw lost its pipeline/layout");
 VkPipeline handle; const Layout* layout; bool placeholder;
 c.GetPipelineAndLayoutByHandle(&p, handle, layout, &placeholder);
 require(handle == 22 && layout == &real && !placeholder, "repeat lookup changed completed pipeline");
 p.creation_status = Status::kFailed;
 c.GetPipelineAndLayoutByHandle(&p, handle, layout, &placeholder);
 require(handle == 0 && layout == nullptr && !placeholder, "failed compilation used a provisional pipeline");
 c.GetPipelineAndLayoutByHandle(nullptr, handle, layout, &placeholder);
 require(handle == 0 && layout == nullptr && !placeholder, "null handle was accepted");
 cfg_vulkan_complete_draws = false;
 p.creation_status = Status::kPending;
 c.GetPipelineAndLayoutByHandle(&p, handle, layout, &placeholder);
 require(placeholder, "legacy skip mode lost its pending indication");
 cfg_vulkan_complete_draws = true;
 for (int i = 0; i != 100; ++i) {
   Pipeline independent; independent.pipeline = 33; independent.pipeline_layout = &real;
   independent.creation_status = Status::kReady;
   c.GetPipelineAndLayoutByHandle(&independent, handle, layout, &placeholder);
   require(handle == 33 && !placeholder, "unrelated preloads delayed a ready draw");
 }
 std::cout << "PASS delayed draw, atomic publication, failure, repeat and independent lookup\n";
}
'''
if __name__ == '__main__':
    print(generate(Path(sys.argv[1])))
