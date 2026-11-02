"""Execute SDK completion/reuse decisions with controlled Vulkan fence results.

Project work: djultra64. Generate, compile and run on the Windows test host.
The tracker and paint prefix come from the supplied SDK, never a copied model.
Only the Vulkan API boundary supplies failures that cannot be requested safely
from a live driver. Removing a completion guard must permit an unsafe pool reset
and fail the contract; a later completed submission must satisfy an earlier one.
"""
from pathlib import Path
import sys

from pipeline_completion_fixture import extract


def generate(sdk):
    header = (sdk / 'include/rex/ui/vulkan/submission_tracker.h').read_text()
    tracker = (sdk / 'src/ui/vulkan/vulkan_submission_tracker.cpp').read_text()
    presenter = (sdk / 'src/ui/vulkan/vulkan_presenter.cpp').read_text()
    common_header = (sdk / 'include/rex/ui/presenter.h').read_text()
    paint = extract(presenter, 'Presenter::PaintResult VulkanPresenter::PaintAndPresentImpl(')
    # Keep the actual wait, selection and vkResetCommandPool call. Later drawing
    # is outside this lifetime contract and needs the real interactive game.
    paint = paint[:paint.index('  VkCommandBuffer draw_command_buffer =')]
    paint += '  return PaintResult::kPresented;\n}\n'
    refresh = extract(presenter, 'bool VulkanPresenter::RefreshGuestOutputImpl(')
    signal = ('void VulkanPresenter::SeedRefreshSignal() {\n'
              '  auto& image_instance = guest_output_images_[0];\n'
              '  image_instance.last_refresher_submission =' +
              refresh.split('  image_instance.last_refresher_submission =', 1)[1]
              .split('  return refresher_succeeded;', 1)[0] + '}\n')
    refresh = refresh[:refresh.index('  if (!image_instance.image) {')]
    refresh += '  return true;\n}\n'
    proof = (extract(presenter, 'bool AwaitGraphicsSubmission(')
             if 'bool AwaitGraphicsSubmission(' in presenter else '')
    report = (extract(common_header, 'void ReportHostGpuLossAfterRefreshFailure()')
              if 'void ReportHostGpuLossAfterRefreshFailure()' in common_header else '')
    notice = header[header.index('/**'):header.index('#include')]
    return (notice + PREFIX + extract(header, 'class VulkanSubmissionTracker {') + ';\n'
            + extract(tracker, 'namespace rex {').removeprefix('namespace rex {')
              .removesuffix('}').replace('namespace ui {\nnamespace vulkan {', '', 1)
              .rsplit('}  // namespace vulkan', 1)[0]
            + proof + PRESENTER.replace('/* loss callback helper */', report)
            + paint + refresh + signal + SUFFIX)


PREFIX = r'''
#include <vulkan/vulkan.h>
#include <atomic>
#include <cassert>
#include <cstdint>
#include <deque>
#include <functional>
#include <iostream>
#include <memory>
#include <string>
#include <utility>
#include <vector>
#define assert_true(x) assert(x)
#define assert_not_null(x) assert((x) != nullptr)
#define assert_not_zero(x) assert(x)
#define REXLOG_ERROR(...) ((void)0)
#define REXLOG_WARN(...) ((void)0)
struct Driver {
  inline static VkResult wait = VK_SUCCESS, status = VK_NOT_READY;
  inline static VkResult create = VK_SUCCESS, signal = VK_SUCCESS, idle = VK_ERROR_UNKNOWN;
  inline static unsigned resets = 0, waits = 0, next_fence = 1;
  inline static unsigned images_destroyed = 0;
  inline static unsigned idles = 0, fatals = 0, losses = 0;
  inline static bool queue_locked = false;
};
struct FatalSignal {};
static VkResult VKAPI_CALL Wait(VkDevice, uint32_t n, const VkFence* fences,
                                VkBool32 all, uint64_t timeout) {
  assert(n == 1 && fences && *fences && all && timeout == UINT64_MAX);
  ++Driver::waits;
  return Driver::wait;
}
static VkResult VKAPI_CALL Status(VkDevice, VkFence fence) {
  assert(fence); return Driver::status;
}
static VkResult VKAPI_CALL ResetFences(VkDevice, uint32_t n, const VkFence* fences) {
  assert(n == 1 && fences && *fences); return VK_SUCCESS;
}
static VkResult VKAPI_CALL CreateFence(VkDevice, const VkFenceCreateInfo* info,
                                      const VkAllocationCallbacks*, VkFence* fence) {
  assert(info && info->sType == VK_STRUCTURE_TYPE_FENCE_CREATE_INFO && !info->flags);
  if (Driver::create != VK_SUCCESS) { *fence = VK_NULL_HANDLE; return Driver::create; }
  *fence = (VkFence)(uintptr_t)Driver::next_fence++; return VK_SUCCESS;
}
static void VKAPI_CALL DestroyFence(VkDevice, VkFence, const VkAllocationCallbacks*) {}
static VkResult VKAPI_CALL ResetPool(VkDevice, VkCommandPool pool, VkCommandPoolResetFlags flags) {
  assert(!Driver::queue_locked);
  assert(pool && flags == 0); ++Driver::resets; return VK_SUCCESS;
}
static VkResult VKAPI_CALL Idle(VkQueue queue) {
  assert(queue && Driver::queue_locked && !Driver::resets && !Driver::images_destroyed);
  ++Driver::idles; return Driver::idle;
}
static VkResult VKAPI_CALL Signal(VkQueue queue, uint32_t count, const VkSubmitInfo* submits, VkFence) {
  assert(queue && Driver::queue_locked);
  assert((!count && !submits) || (count == 1 && submits && !submits->commandBufferCount));
  return Driver::signal;
}
namespace rex {
[[noreturn]] inline void FatalError(const char*) {
  assert(!Driver::queue_locked); ++Driver::fatals; throw FatalSignal{};
}
namespace ui { namespace vulkan {
struct VulkanDevice {
  struct Queue {
    struct Acquisition {
      Acquisition() { assert(!Driver::queue_locked); Driver::queue_locked = true; }
      ~Acquisition() { Driver::queue_locked = false; }
      VkQueue queue() const { assert(Driver::queue_locked); return (VkQueue)(uintptr_t)1; }
    };
  };
  struct Properties {} properties_;
  struct Functions {
    PFN_vkWaitForFences vkWaitForFences = Wait;
    PFN_vkGetFenceStatus vkGetFenceStatus = Status;
    PFN_vkResetFences vkResetFences = ResetFences;
    PFN_vkCreateFence vkCreateFence = CreateFence;
    PFN_vkDestroyFence vkDestroyFence = DestroyFence;
    PFN_vkResetCommandPool vkResetCommandPool = ResetPool;
    PFN_vkQueueWaitIdle vkQueueWaitIdle = Idle;
    PFN_vkQueueSubmit vkQueueSubmit = Signal;
  } table;
  const Functions& functions() const { return table; }
  const Properties& properties() const { return properties_; }
  VkDevice device() const { return (VkDevice)(uintptr_t)1; }
  uint32_t queue_family_graphics_compute() const { return 3; }
  Queue::Acquisition AcquireQueue(uint32_t family, uint32_t index) const {
    assert(family == 3 && index == 0); return {};
  }
};
namespace util {
inline VkExtent2D GetMax2DFramebufferExtent(const VulkanDevice::Properties&) { return {4096,4096}; }
template<class F, class H> void DestroyAndNullHandle(F f, VkDevice d, H& h) {
  if (h) f(d, h, nullptr); h = VK_NULL_HANDLE;
}
}
'''

PRESENTER = r'''
struct Presenter {
  enum class PaintResult { kPresented, kNotPresented, kGpuLostResponsible };
  std::function<void(bool,bool)> host_gpu_loss_callback_ = [](bool responsible,bool ui) {
    assert(responsible && !ui && !Driver::queue_locked); ++Driver::losses;
  };
  /* loss callback helper */
};
class VulkanPresenter : public Presenter {
 public:
  struct GuestOutputRefreshContext {};
  struct Image {
    VkExtent2D extent() const { return {64,64}; }
    ~Image() { ++Driver::images_destroyed; }
  };
  struct GuestOutputImageInstance {
    std::unique_ptr<Image> image{new Image};
    uint64_t last_refresher_submission = 1;
  };
  struct PaintContext {
    struct Submission {
      VkCommandPool draw_command_pool() const { return (VkCommandPool)(uintptr_t)1; }
    };
    VulkanSubmissionTracker submission_tracker;
    std::vector<std::unique_ptr<Submission>> submissions;
    explicit PaintContext(const VulkanDevice* d) : submission_tracker(d) {
      for (int i=0; i<3; ++i) submissions.emplace_back(new Submission);
    }
  } paint_context_;
  VulkanSubmissionTracker guest_output_image_refresher_submission_tracker_;
  GuestOutputImageInstance guest_output_images_[1];
  const VulkanDevice* vulkan_device_;
  explicit VulkanPresenter(const VulkanDevice* d) : paint_context_(d),
      guest_output_image_refresher_submission_tracker_(d), vulkan_device_(d) {}
  PaintResult PaintAndPresentImpl(bool execute_ui_drawers);
  void SeedRefreshSignal();
  bool RefreshGuestOutputImpl(uint32_t mailbox_index, uint32_t width, uint32_t height,
      std::function<bool(GuestOutputRefreshContext&)> refresher, bool& is_8bpc_out_ref);
};
'''

SUFFIX = r'''
}}}
using namespace rex::ui::vulkan;
static int fail(const char* reason) { std::cerr << "FAIL: " << reason << '\n'; return 1; }
int main(int argc, char** argv) {
  if (argc != 2) return 2;
  const std::string mode = argv[1];
  VulkanDevice device;
  VulkanPresenter painter(&device);
  auto& tracker = mode.rfind("resize_",0) == 0
      ? painter.guest_output_image_refresher_submission_tracker_
      : painter.paint_context_.submission_tracker;
  const bool signal_case = mode == "resize_signal_failure" || mode == "resize_null_fence";
  if (signal_case) {
    if (mode == "resize_signal_failure") Driver::signal = VK_ERROR_UNKNOWN;
    else Driver::create = VK_ERROR_OUT_OF_HOST_MEMORY;
    painter.SeedRefreshSignal();
    Driver::signal = Driver::create = VK_SUCCESS;
    if (tracker.GetCurrentSubmission() != 2 || tracker.UpdateAndGetCompletedSubmission())
      return fail("missing-signal setup must advance without inventing completion");
  } else if (mode != "paint_initial" && mode != "dropped_submission") {
    for (int i=0; i<3; ++i) { auto fence = tracker.AcquireFenceToAdvanceSubmission(); }
  }
  int result = 0;
  if (mode == "await_reached") {
    Driver::status = VK_SUCCESS;
    if (tracker.UpdateAndGetCompletedSubmission() != 3) return fail("fixture completion setup");
    if (!tracker.AwaitSubmissionCompletion(1)) result = fail("submission 3 completed, but waiting for 1 failed");
  } else if (mode == "paint_wait_failure") {
    Driver::wait = VK_ERROR_UNKNOWN;
    bool fatal = false;
    try { painter.PaintAndPresentImpl(false); } catch (const FatalSignal&) { fatal = true; }
    if (Driver::resets) result = fail("paint reset its pool without completion proof");
    else if (!fatal) result = fail("failed completion proof must not become an endless paint retry");
  } else if (mode == "paint_recovery" || mode == "paint_device_lost") {
    Driver::wait = mode == "paint_device_lost" ? VK_ERROR_DEVICE_LOST : VK_ERROR_UNKNOWN;
    Driver::status = VK_NOT_READY;
    Driver::idle = mode == "paint_device_lost" ? VK_ERROR_DEVICE_LOST : VK_SUCCESS;
    const auto painted = painter.PaintAndPresentImpl(false);
    if (mode == "paint_device_lost") {
      if (painted != Presenter::PaintResult::kGpuLostResponsible || Driver::resets || Driver::losses)
        result = fail("paint must propagate terminal GPU loss without reusing its pool");
    } else if (painted != Presenter::PaintResult::kPresented || Driver::resets != 1 || Driver::idles != 1)
      result = fail("successful queue completion proof must recover paint");
  } else if (mode == "paint_ready" || mode == "paint_initial") {
    const auto presented = painter.PaintAndPresentImpl(false);
    if (Driver::resets != 1 || presented != Presenter::PaintResult::kPresented)
      result = fail("safe paint must remain usable");
    if (mode == "paint_initial" && Driver::waits) result = fail("unused pool must not add a fence wait");
  } else if (mode == "wait_failure_pending") {
    Driver::wait = VK_ERROR_UNKNOWN;
    if (tracker.AwaitSubmissionCompletion(1) || tracker.UpdateAndGetCompletedSubmission())
      result = fail("failed wait invented completion");
  } else if (mode == "dropped_submission") {
    { auto fence = tracker.AcquireFenceToAdvanceSubmission(); fence.SubmissionFailedOrDropped(); }
    if (tracker.GetCurrentSubmission() != 1 || tracker.UpdateAndGetCompletedSubmission())
      result = fail("dropped submission changed the timeline");
    { auto retry = tracker.AcquireFenceToAdvanceSubmission(); }
    Driver::status = VK_SUCCESS;
    if (!tracker.AwaitSubmissionCompletion(1)) result = fail("dropped submission prevented a safe retry");
  } else if (signal_case || mode == "resize_recovery" || mode == "resize_device_lost") {
    Driver::wait = mode == "resize_device_lost" ? VK_ERROR_DEVICE_LOST : VK_ERROR_UNKNOWN;
    Driver::idle = mode == "resize_device_lost" ? VK_ERROR_DEVICE_LOST : VK_SUCCESS;
    bool is_8bit = false;
    const auto resized = painter.RefreshGuestOutputImpl(0,1280,64,nullptr,is_8bit);
    if (mode == "resize_device_lost") {
      if (resized || Driver::images_destroyed || Driver::losses != 1)
        result = fail("resize must report terminal GPU loss and retain its image");
    } else if (!resized || Driver::images_destroyed != 1 || Driver::idles != 1)
      result = fail("queue completion proof must recover resized output");
    if (signal_case && tracker.UpdateAndGetCompletedSubmission())
      result = fail("queue-idle recovery invented a tracker fence signal");
  } else if (mode == "resize_wait_failure" || mode == "resize_ready" || mode == "resize_unchanged") {
    Driver::wait = mode == "resize_ready" ? VK_SUCCESS : VK_ERROR_UNKNOWN;
    bool is_8bit = false;
    bool fatal = false, resized = false;
    try { resized = painter.RefreshGuestOutputImpl(0,
        mode == "resize_unchanged" ? 64 : 1280,64,nullptr,is_8bit); }
    catch (const FatalSignal&) { fatal = true; }
    if (mode == "resize_wait_failure") {
      if (Driver::images_destroyed || !painter.guest_output_images_[0].image)
        result = fail("resize destroyed an image without completion proof");
      else if (!fatal || resized) result = fail("failed completion proof must not become an endless resize retry");
    } else if (mode == "resize_ready") {
      if (!resized || Driver::images_destroyed != 1)
        result = fail("completed resize did not retire its old image");
    } else if (!resized || Driver::images_destroyed || Driver::waits)
      result = fail("unchanged output must not add waits or retire its image");
  } else return 2;
  if (mode == "await_reached" || mode == "paint_ready" || mode == "paint_initial" ||
      mode == "wait_failure_pending" || mode == "resize_ready" || mode == "resize_unchanged" ||
      mode == "dropped_submission") {
    if (Driver::idles) result = fail("healthy/unchanged work added a queue-wide wait");
  }
  // All test-owned work is complete before ordinary tracker destruction.
  Driver::wait = Driver::status = VK_SUCCESS;
  tracker.AwaitAllSubmissionsCompletion();
  if (!result) std::cout << "PASS " << mode << '\n';
  return result;
}
'''


if __name__ == '__main__':
    Path(sys.argv[2]).write_text(generate(Path(sys.argv[1])))
