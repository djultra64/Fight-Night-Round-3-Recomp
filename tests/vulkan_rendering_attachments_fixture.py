"""Native attachment contracts through real SDK construction and deferred replay.

Project work: djultra64. Compile/run on Windows. The spy substitutes only the
Vulkan command boundary; attachments and command serialization use SDK methods.
"""
from pathlib import Path
import re
import sys
from pipeline_completion_fixture import extract


def generate(sdk):
    root = sdk / 'src/graphics/vulkan'
    inc = sdk / 'include/rex/graphics/vulkan'
    cache = (root / 'render_target_cache.cpp').read_text()
    header = (inc / 'render_target_cache.h').read_text()
    deferred = (root / 'deferred_command_buffer.cpp').read_text()
    deferred_header = (inc / 'deferred_command_buffer.h').read_text()
    fields = '\n'.join(f'    PFN_{name} {name} = nullptr;' for name in
                       sorted(set(re.findall(r'dfn\.(vk\w+)', deferred))))
    constants = []
    for name in ('kColorDrawLayout', 'kDepthDrawLayout'):
        start = header.index('static constexpr VkImageLayout ' + name)
        constants.append(header[start:header.index(';', start) + 1])
    namespace = 'namespace rex::graphics::vulkan {'
    methods = extract(deferred, namespace)[len(namespace):-1]
    notice = cache[cache.index('/**'):cache.index('#include')]
    return (notice + PREFIX.replace('/* API fields */', fields)
            + TARGET.replace('/* real layouts */', '\n'.join(constants))
            + extract(cache, 'void VulkanRenderTargetCache::GetLastUpdateRenderingAttachments(')
            + '\n' + extract(deferred_header, 'class DeferredCommandBuffer {') + ';\n'
            + methods + MAIN)


PREFIX = r'''
#include <vulkan/vulkan.h>
#include <array>
#include <cassert>
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <vector>
#define assert_null(x) assert((x) == nullptr)
#define assert_unhandled_case(x) std::abort()
namespace rex {
template<typename T> constexpr T align(T value, size_t alignment) {
  return T((value + alignment - 1) & ~(alignment - 1));
}
}
namespace xenos { constexpr uint32_t kMaxColorRenderTargets = 4; }
static std::vector<VkRenderingAttachmentInfo> received_colors;
static VkRenderingAttachmentInfo received_depth{}, received_stencil{};
static unsigned received_calls = 0;
static bool received_has_depth = false, received_has_stencil = false;
static void VKAPI_CALL Receive(VkCommandBuffer, const VkRenderingInfo* info) {
  ++received_calls;
  assert(info && info->sType == VK_STRUCTURE_TYPE_RENDERING_INFO && !info->pNext);
  received_colors.clear();
  if (info->colorAttachmentCount)
    received_colors.assign(info->pColorAttachments, info->pColorAttachments + info->colorAttachmentCount);
  received_has_depth = info->pDepthAttachment != nullptr;
  received_has_stencil = info->pStencilAttachment != nullptr;
  if (received_has_depth) received_depth = *info->pDepthAttachment;
  if (received_has_stencil) received_stencil = *info->pStencilAttachment;
}
namespace ui { namespace vulkan {
struct VulkanDevice {
  struct Functions {
/* API fields */
  } dfn;
  VulkanDevice() { dfn.vkCmdBeginRendering = Receive; }
  const Functions& functions() const { return dfn; }
};
}}
class VulkanCommandProcessor {
 public:
  const ui::vulkan::VulkanDevice* GetVulkanDevice() const {
    static ui::vulkan::VulkanDevice value; return &value;
  }
};
'''
TARGET = r'''
struct RenderTarget {};
struct VulkanRenderTarget : RenderTarget {
  /* real layouts */
  VkImageView color = VK_NULL_HANDLE, depth = VK_NULL_HANDLE;
  VkImageView view_depth_color() const { return color; }
  VkImageView view_depth_stencil() const { return depth; }
};
class VulkanRenderTargetCache {
 public:
  struct RenderPassKey { uint32_t depth_and_color_used = 0; } last_update_render_pass_key_;
  std::array<RenderTarget*, 5> targets{};
  RenderTarget* const* last_update_accumulated_render_targets() const { return targets.data(); }
  void GetLastUpdateRenderingAttachments(VkRenderingAttachmentInfo*, uint32_t*,
                                        VkRenderingAttachmentInfo*, VkRenderingAttachmentInfo*) const;
};
'''
MAIN = r'''
static bool Check(bool ok, const char* message) {
  if (!ok) std::cerr << message << '\n'; return ok;
}
int main(int argc, char** argv) {
  if (argc != 2) return 2;
  unsigned mode = unsigned(std::strtoul(argv[1], nullptr, 10));
  if (mode > 33) return 2;
  bool missing = mode >= 32;
  unsigned mask = missing ? 3 : mode & 15;
  bool with_depth = missing ? (mode & 1) != 0 : (mode & 16) != 0;
  VulkanRenderTargetCache cache;
  cache.last_update_render_pass_key_.depth_and_color_used = mask * 2 + unsigned(with_depth);
  VulkanRenderTarget images[5];
  for (unsigned i = 0; i < 5; ++i) {
    images[i].color = (VkImageView)(uintptr_t)(0x100 + i);
    images[i].depth = (VkImageView)(uintptr_t)(0x200 + i);
    cache.targets[i] = &images[i];
  }
  if (missing) cache.targets[1] = nullptr;
  std::array<VkRenderingAttachmentInfo, 4> colors;
  VkRenderingAttachmentInfo depth, stencil;
  std::memset(colors.data(), 0xcc, sizeof(colors));
  std::memset(&depth, 0xcc, sizeof(depth)); std::memset(&stencil, 0xcc, sizeof(stencil));
  uint32_t count = 999;
  cache.GetLastUpdateRenderingAttachments(colors.data(), &count, &depth, &stencil);
  VkRenderingInfo info{VK_STRUCTURE_TYPE_RENDERING_INFO};
  info.renderArea.extent = {1, 1}; info.layerCount = 1;
  info.colorAttachmentCount = count; info.pColorAttachments = count ? colors.data() : nullptr;
  info.pDepthAttachment = depth.sType == VK_STRUCTURE_TYPE_RENDERING_ATTACHMENT_INFO ? &depth : nullptr;
  info.pStencilAttachment = stencil.sType == VK_STRUCTURE_TYPE_RENDERING_ATTACHMENT_INFO ? &stencil : nullptr;
  VulkanCommandProcessor processor; DeferredCommandBuffer commands(processor, 8);
  commands.CmdVkBeginRendering(&info);
  // Overwrite the caller-owned data before executing the recorded command.
  std::memset(colors.data(), 0xdd, sizeof(colors));
  std::memset(&depth, 0xdd, sizeof(depth)); std::memset(&stencil, 0xdd, sizeof(stencil));
  commands.Execute((VkCommandBuffer)1);
  unsigned expected_count = 0;
  for (unsigned i = 0; i < 4; ++i)
    if ((mask & (1u << i)) && !(missing && i == 0)) expected_count = i + 1;
  bool ok = Check(received_calls == 1, "deferred Vulkan call missing");
  ok &= Check(received_colors.size() == expected_count, "color slots packed or count changed");
  for (unsigned i = 0; i < received_colors.size(); ++i) {
    const auto& color = received_colors[i];
    bool used = (mask & (1u << i)) && !(missing && i == 0);
    ok &= Check(color.sType == VK_STRUCTURE_TYPE_RENDERING_ATTACHMENT_INFO, "invalid color attachment header");
    ok &= Check(color.pNext == nullptr, "unexpected extension chain");
    ok &= Check(color.imageView == (used ? images[i + 1].color : VK_NULL_HANDLE), "image slot changed");
    if (used) ok &= Check(color.imageLayout == VulkanRenderTarget::kColorDrawLayout &&
                         color.loadOp == VK_ATTACHMENT_LOAD_OP_LOAD &&
                         color.storeOp == VK_ATTACHMENT_STORE_OP_STORE, "color payload changed");
  }
  ok &= Check(received_has_depth == with_depth && received_has_stencil == with_depth,
              "absent depth/stencil became present or used depth lost");
  if (with_depth) {
    ok &= Check(received_depth.sType == VK_STRUCTURE_TYPE_RENDERING_ATTACHMENT_INFO &&
                received_stencil.sType == VK_STRUCTURE_TYPE_RENDERING_ATTACHMENT_INFO &&
                received_depth.imageView == images[0].depth &&
                received_stencil.imageView == images[0].depth, "depth/stencil replay changed");
  }
  return ok ? 0 : 1;
}
'''

if __name__ == '__main__':
    Path(sys.argv[2]).write_text(generate(Path(sys.argv[1])), encoding='utf-8')
