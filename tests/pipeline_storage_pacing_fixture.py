"""Generate private SDK method fixture; compile/run only on an authorized build host.

Work: djultra64. No SDK implementation is committed in this file. Usage:
python tests/pipeline_storage_pacing_fixture.py SDK_ROOT /tmp/storage_pacing.cpp
c++ -std=c++20 -pthread /tmp/storage_pacing.cpp -o /tmp/storage_pacing
/tmp/storage_pacing

Run against unpatched and patched SDK trees for red/green. Vulkan data retrieval
is replaced with a blocking persistence seam; the actual storage worker and
submission methods are extracted unchanged. Shader flushes use real stdio.
"""
from pathlib import Path
import sys


def method(text, name):
    start = text.index('void VulkanPipelineCache::' + name + '(')
    brace = text.index('{', start)
    depth = 1
    end = brace + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]


def generate(sdk):
    source = (sdk / 'src/graphics/vulkan/pipeline_cache.cpp').read_text()
    methods = '\n'.join(method(source, name) for name in ('EndSubmission', 'StorageWriteThread'))
    return PREFIX + methods + SUFFIX


PREFIX = r'''
#include <algorithm>
#include <atomic>
#include <cassert>
#include <chrono>
#include <condition_variable>
#include <cstdio>
#include <cstdint>
#include <cstdlib>
#include <memory>
#include <cstring>
#include <deque>
#include <future>
#include <iostream>
#include <mutex>
#include <thread>
#include <vector>
using namespace std::chrono_literals;
#define assert_not_null(x) assert(x)
namespace rex::thread { template<class T> void Wait(T*, bool) {} }
namespace memory { void copy_and_swap(uint32_t*, const uint32_t*, uint32_t) {} }
struct Shader { uint64_t ucode_data_hash() const { return 0; }
 uint32_t ucode_dword_count() const { return 0; } uint32_t type() const { return 0; }
 const uint32_t* ucode_dwords() const { return nullptr; } };
struct ShaderStoredHeader { uint64_t ucode_data_hash; uint32_t ucode_dword_count, type; };
struct PipelineStoredDescription { uint64_t data = 0x1234; };
struct Event { void Reset() {} };
struct VulkanPipelineCache {
 std::mutex storage_write_request_lock_, creation_request_lock_, save_lock;
 std::condition_variable storage_write_request_cond_, creation_request_cond_, save_cond;
 std::deque<const Shader*> storage_write_shader_queue_;
 std::deque<PipelineStoredDescription> storage_write_pipeline_queue_;
 bool storage_write_flush_shaders_ = false, storage_write_flush_pipelines_ = false;
 bool storage_write_driver_cache_ = false, storage_write_thread_shutdown_ = false;
 bool shader_storage_file_flush_needed_ = false, pipeline_storage_file_flush_needed_ = false;
 uint32_t driver_cache_submissions_ = 0;
 FILE* shader_storage_file_ = std::tmpfile();
 FILE* pipeline_storage_file_ = std::tmpfile();
 std::vector<int> creation_threads_;
 bool startup_loading_ = false, creation_completion_set_event_ = false;
 size_t creation_threads_busy_ = 0;
 std::unique_ptr<Event> creation_completion_event_;
 std::atomic<int> saves{0};
 bool hold_save = false, save_entered = false;
 std::thread::id saver;
 void SaveDriverCache() { std::unique_lock lock(save_lock); saver = std::this_thread::get_id();
  save_entered = true; save_cond.notify_all(); save_cond.wait(lock, [&]{ return !hold_save; }); ++saves; }
 void CreateQueuedPipelinesOnProcessorThread() {}
 void ProcessDeferredPipelineDestructions(bool) {}
 void EndSubmission(); void StorageWriteThread();
 ~VulkanPipelineCache() { fclose(shader_storage_file_); fclose(pipeline_storage_file_); }
};
void require(bool b, const char* s) { if (!b) { std::cerr << s << '\n'; std::exit(1); } }
'''

SUFFIX = r'''
int main() {
 // Flush-only work must become visible on disk with no additional notification.
 { VulkanPipelineCache c;
   // stdio output is buffered until the actual worker calls fflush.
   char shader_buffer[4096], pipeline_buffer[4096];
   setvbuf(c.shader_storage_file_, shader_buffer, _IOFBF, sizeof(shader_buffer));
   setvbuf(c.pipeline_storage_file_, pipeline_buffer, _IOFBF, sizeof(pipeline_buffer));
   fputs("shader", c.shader_storage_file_); fputs("pipeline", c.pipeline_storage_file_);
   c.storage_write_flush_shaders_ = c.storage_write_flush_pipelines_ = true;
   std::thread writer([&]{ c.StorageWriteThread(); });
   // Inspect duplicate descriptors: no data races on FILE and no accidental flush.
   auto deadline = std::chrono::steady_clock::now() + 1s;
   bool visible = false;
   while (std::chrono::steady_clock::now() < deadline) {
     char a[8] = {}, b[8] = {};
     visible = pread(fileno(c.shader_storage_file_), a, 6, 0) == 6 &&
               pread(fileno(c.pipeline_storage_file_), b, 8, 0) == 8;
     if (visible) break;
     std::this_thread::sleep_for(1ms);
   }
   { std::lock_guard lock(c.storage_write_request_lock_); c.storage_write_thread_shutdown_ = true; }
   c.storage_write_request_cond_.notify_one(); writer.join();
   require(visible, "flush-only request stalled without a second notification");
 }
 // A periodic save must not execute on, or block, the submission thread.
 { VulkanPipelineCache c;
   c.driver_cache_submissions_ = 599; c.hold_save = true;
   std::thread writer([&]{ c.StorageWriteThread(); });
   auto submit = std::async(std::launch::async, [&]{ c.EndSubmission(); return std::this_thread::get_id(); });
   bool returned = submit.wait_for(200ms) == std::future_status::ready;
   { std::unique_lock lock(c.save_lock);
     c.save_cond.wait_for(lock, 1s, [&]{return c.save_entered;}); c.hold_save = false; }
   c.save_cond.notify_all(); auto submit_id = submit.get();
   { std::lock_guard lock(c.storage_write_request_lock_); c.storage_write_thread_shutdown_ = true; }
   c.storage_write_request_cond_.notify_one(); writer.join();
   require(returned && c.saves == 1 && c.saver != submit_id, "periodic save blocked submission or ran on submission thread");
 }
 // Multiple periodic requests before the writer runs must coalesce to one save.
 { VulkanPipelineCache c;
   for (int i = 0; i < 1800; ++i) c.EndSubmission();
   c.storage_write_thread_shutdown_ = true;
   std::thread writer([&]{ c.StorageWriteThread(); }); writer.join();
   require(c.saves == 1, "periodic requests did not coalesce");
 }
 // Shutdown drains queued records and a coalesced save before joining/closing.
 { VulkanPipelineCache c;
   Shader shader; c.storage_write_shader_queue_.push_back(&shader);
   c.storage_write_pipeline_queue_.emplace_back();
   c.storage_write_flush_shaders_ = c.storage_write_flush_pipelines_ = true;
   c.storage_write_driver_cache_ = true; c.storage_write_thread_shutdown_ = true;
   std::thread writer([&]{ c.StorageWriteThread(); }); writer.join();
   require(c.saves == 1 && ftell(c.shader_storage_file_) == sizeof(ShaderStoredHeader) &&
           ftell(c.pipeline_storage_file_) == sizeof(PipelineStoredDescription), "shutdown discarded pending work");
 }
 std::cout << "storage pacing runtime regressions passed\n";
}
'''
# POSIX fixture only, for the Linux HTPC build host.
PREFIX = '#include <unistd.h>\n' + PREFIX
if __name__ == '__main__':
    Path(sys.argv[2]).write_text(generate(Path(sys.argv[1])))
