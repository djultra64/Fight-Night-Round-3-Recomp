"""Native contracts for the actual SDK readback eviction method.

Project work: djultra64. Generate/compile/run on Windows only. Vulkan resource
retirement is observed at the API boundary; the eviction algorithm is extracted
from the prepared SDK rather than reimplemented in this fixture.
"""
from pathlib import Path
import sys
from pipeline_completion_fixture import extract


def generate(sdk):
    source = (sdk / 'src/graphics/vulkan/command_processor.cpp').read_text()
    header = (sdk / 'include/rex/graphics/vulkan/command_processor.h').read_text()
    method = extract(source, 'void VulkanCommandProcessor::EvictOldReadbackBuffers(')
    record = extract(header, 'struct ReadbackBuffer {') + ';\n'
    notice = source[source.index('/**'):source.index('#if')]
    return notice + PREFIX + record + OWNER + method + MAIN


PREFIX = r'''
#include <vulkan/vulkan.h>
#include <cassert>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <string>
#include <unordered_map>
#include <unordered_set>
#define REXGPU_WARN(...) ((void)0)
struct Observed {
  inline static std::unordered_set<uintptr_t> buffers, memories, mappings;
};
namespace ui { namespace vulkan {
struct VulkanDevice {
  struct Functions {
    static void vkUnmapMemory(VkDevice, VkDeviceMemory memory) {
      assert(memory); assert(Observed::mappings.insert((uintptr_t)memory).second);
    }
    static void vkDestroyBuffer(VkDevice, VkBuffer buffer, const VkAllocationCallbacks*) {
      assert(buffer); assert(Observed::buffers.insert((uintptr_t)buffer).second);
    }
    static void vkFreeMemory(VkDevice, VkDeviceMemory memory, const VkAllocationCallbacks*) {
      assert(memory); assert(Observed::memories.insert((uintptr_t)memory).second);
    }
  };
  const Functions& functions() const { static Functions value; return value; }
  VkDevice device() const { return (VkDevice)1; }
};
}}
class VulkanCommandProcessor {
 public:
'''
OWNER = r'''
  uint64_t frame_current_ = 100, frame_completed_ = 97, submission_completed_ = 8;
  static constexpr size_t kMaxReadbackBuffers = 256;
  static constexpr uint64_t kReadbackBufferEvictionAgeFrames = 60;
  std::unordered_map<uint64_t, ReadbackBuffer> buffers;
  const ui::vulkan::VulkanDevice* GetVulkanDevice() const {
    static ui::vulkan::VulkanDevice value; return &value;
  }
  void EvictOldReadbackBuffers(std::unordered_map<uint64_t, ReadbackBuffer>& buffer_map);
  void Add(uint64_t key, uint64_t frame, uint64_t written0, uint64_t written1) {
    auto& entry = buffers[key]; entry.last_used_frame = frame;
    entry.submission_written[0] = written0; entry.submission_written[1] = written1;
    for (unsigned i = 0; i < 2; ++i) {
      uintptr_t value = key * 4 + i + 1;
      entry.buffers[i] = (VkBuffer)value; entry.memories[i] = (VkDeviceMemory)value;
      entry.mapped_data[i] = (void*)value; entry.sizes[i] = 4096;
    }
  }
};
'''
MAIN = r'''
static bool Check(bool ok, const char* message) {
  if (!ok) std::cerr << message << '\n'; return ok;
}
int main(int argc, char** argv) {
  if (argc != 2) return 2;
  std::string mode = argv[1]; VulkanCommandProcessor owner;
  size_t count = 1, expected = 1; uint64_t frame = 80, written0 = 8, written1 = 8;
  if (mode == "empty") { count = 0; expected = 0; }
  else if (mode == "pressure_pending0") { count = expected = 257; written0 = 9; }
  else if (mode == "pressure_pending1") { count = expected = 257; written1 = 9; }
  else if (mode == "pressure_recent") { count = expected = 257; frame = 99; }
  else if (mode == "age_pending0") { frame = 30; written0 = 9; }
  else if (mode == "age_pending1") { frame = 30; written1 = 9; }
  else if (mode == "pressure_completed") { count = 257; expected = 256; }
  else if (mode == "age_completed") { frame = 30; expected = 0; }
  else if (mode == "recent_under_limit") { frame = 99; }
  else if (mode == "age_boundary") { frame = 40; }
  else if (mode == "completion_boundary") { count = 257; expected = 256; frame = 97; }
  else if (mode == "mixed_pressure") { count = expected = 257; written0 = 9; }
  else if (mode == "rescan") { count = expected = 257; written0 = 9; }
  else return 2;
  for (size_t i = 0; i < count; ++i) owner.Add(i, frame, written0, written1);
  uint64_t eligible_key = 0;
  if (mode == "mixed_pressure") {
    // Put the only completed entry after pending entries in this container's
    // actual iteration order. Correct retirement must skip pending entries.
    for (const auto& entry : owner.buffers) eligible_key = entry.first;
    owner.buffers.at(eligible_key).submission_written[0] = 8; expected = 256;
  }
  owner.EvictOldReadbackBuffers(owner.buffers);
  bool ok = Check(owner.buffers.size() == expected, "unexpected retained count");
  size_t retired = count - expected;
  ok &= Check(Observed::buffers.size() == retired * 2 &&
              Observed::memories.size() == retired * 2 &&
              Observed::mappings.size() == retired * 2, "unsafe or incomplete resource retirement");
  if (mode == "mixed_pressure") {
    ok &= Check(owner.buffers.find(eligible_key) == owner.buffers.end(), "completed entry not reclaimed under pressure");
    for (size_t i = 0; i < count; ++i)
      if (i != eligible_key)
        ok &= Check(owner.buffers.find(i) != owner.buffers.end(), "pending entry reclaimed");
  }
  if (mode == "rescan") {
    owner.submission_completed_ = 9;
    owner.EvictOldReadbackBuffers(owner.buffers);
    ok &= Check(owner.buffers.size() == 256 && Observed::buffers.size() == 2 &&
                Observed::memories.size() == 2 && Observed::mappings.size() == 2,
                "deferred retirement failed after completion advanced");
  }
  return ok ? 0 : 1;
}
'''

if __name__ == '__main__':
    Path(sys.argv[2]).write_text(generate(Path(sys.argv[1])), encoding='utf-8')
