"""Exercise actual presenter resource replacement blocks with completion failures.

Project work: djultra64. Reuse the real tracker/helper from completion contracts.
"""
from pipeline_completion_fixture import extract
from vulkan_submission_completion_fixture import generate as completion_generate


def generate(sdk):
    presenter = (sdk / 'src/ui/vulkan/vulkan_presenter.cpp').read_text()
    paint = extract(presenter, 'Presenter::PaintResult VulkanPresenter::PaintAndPresentImpl(')
    replacement = paint[paint.index('// Need to replace immediately'):]
    intermediate = extract(replacement, 'if (intermediate_image_ptr_ref) {')
    pipeline = extract(paint[paint.index('// Ensure the pipeline exists for the final effect'):],
                       'if (swapchain_effect_pipeline.swapchain_pipeline !=')
    generated = completion_generate(sdk)
    generated = generated.replace('inline static unsigned images_destroyed = 0;',
        'inline static unsigned images_destroyed=0, framebuffers_destroyed=0, pipelines_destroyed=0;')
    generated = generated.replace('!Driver::resets && !Driver::images_destroyed);',
        '!Driver::resets && !Driver::images_destroyed && !Driver::framebuffers_destroyed && !Driver::pipelines_destroyed);')
    generated = generated.replace('PFN_vkQueueSubmit vkQueueSubmit = Signal;', '''PFN_vkQueueSubmit vkQueueSubmit = Signal;
    static void vkDestroyFramebuffer(VkDevice,VkFramebuffer,const VkAllocationCallbacks*){++Driver::framebuffers_destroyed;}
    static void vkDestroyPipeline(VkDevice,VkPipeline,const VkAllocationCallbacks*){++Driver::pipelines_destroyed;}''')
    generated = generated.replace('explicit PaintContext(const VulkanDevice* d)', '''
    std::unique_ptr<Image> guest_output_intermediate_images[1] = {std::unique_ptr<Image>(new Image)};
    VkFramebuffer guest_output_intermediate_framebuffers[1]={(VkFramebuffer)1};
    uint64_t guest_output_intermediate_image_last_submission=3,guest_output_image_paint_last_submission=3;
    VkFormat swapchain_render_pass_format=VK_FORMAT_B8G8R8A8_UNORM;
    struct Pipeline {VkPipeline swapchain_pipeline=(VkPipeline)2;VkFormat swapchain_format=VK_FORMAT_R8G8B8A8_UNORM;} pipeline;
    explicit PaintContext(const VulkanDevice* d)''')
    generated = generated.replace('PaintResult PaintAndPresentImpl(bool execute_ui_drawers);',
        'PaintResult PaintAndPresentImpl(bool execute_ui_drawers);\n  PaintResult RetireIntermediate();\n  PaintResult RetirePipeline();')
    methods = '''Presenter::PaintResult VulkanPresenter::RetireIntermediate(){
 const auto& dfn=vulkan_device_->functions();auto device=vulkan_device_->device();size_t i=0;
 auto& intermediate_image_ptr_ref=paint_context_.guest_output_intermediate_images[i];
''' + intermediate + '''
 return PaintResult::kPresented;
}
Presenter::PaintResult VulkanPresenter::RetirePipeline(){
 const auto& dfn=vulkan_device_->functions();auto device=vulkan_device_->device();
 auto& swapchain_effect_pipeline=paint_context_.pipeline;
''' + pipeline + '''
 return PaintResult::kPresented;
}
'''
    generated = generated.replace('}}}\nusing namespace rex::ui::vulkan;',
                                  methods + '}}}\nusing namespace rex::ui::vulkan;')
    generated = generated.replace('if (mode == "await_reached") {', CASE + '\n  } else if (mode == "await_reached") {')
    return generated


CASE = r'''if (mode.rfind("intermediate_",0)==0 || mode.rfind("pipeline_",0)==0) {
    const bool intermediate=mode.rfind("intermediate_",0)==0;
    const auto outcome=mode.substr(mode.find('_')+1);
    Driver::wait=outcome=="ready"?VK_SUCCESS:outcome=="lost"?VK_ERROR_DEVICE_LOST:VK_ERROR_UNKNOWN;
    Driver::idle=outcome=="recovery"?VK_SUCCESS:outcome=="lost"?VK_ERROR_DEVICE_LOST:VK_ERROR_UNKNOWN;
    bool fatal=false;auto painted=Presenter::PaintResult::kNotPresented;
    try {painted=intermediate?painter.RetireIntermediate():painter.RetirePipeline();}
    catch(const FatalSignal&){fatal=true;}
    const bool destroyed=intermediate?Driver::images_destroyed||Driver::framebuffers_destroyed:Driver::pipelines_destroyed;
    const bool alive=intermediate?bool(painter.paint_context_.guest_output_intermediate_images[0]):painter.paint_context_.pipeline.swapchain_pipeline!=VK_NULL_HANDLE;
    if(outcome=="lost" || outcome=="failure") {
      if(destroyed||!alive)result=fail("replacement destroyed a resource without completion proof");
      else if(outcome=="lost"&&(fatal||painted!=Presenter::PaintResult::kGpuLostResponsible))result=fail("replacement must propagate GPU loss");
      else if(outcome=="failure"&&!fatal)result=fail("failed completion proof became a silent replacement/retry");
    } else {
      if(fatal||!destroyed||alive||painted!=Presenter::PaintResult::kPresented)result=fail("proven-complete replacement did not retire resource");
      if(intermediate&&(Driver::images_destroyed!=1||Driver::framebuffers_destroyed!=1||painter.paint_context_.guest_output_intermediate_framebuffers[0]!=VK_NULL_HANDLE))result=fail("proven-complete intermediate retirement must release both image and framebuffer exactly once");
      if(!intermediate&&Driver::pipelines_destroyed!=1)result=fail("proven-complete pipeline retirement must destroy exactly once");
      if(outcome=="ready"&&Driver::idles)result=fail("healthy replacement added queue-idle wait");
      if(outcome=="recovery"&&Driver::idles!=1)result=fail("recovery lacks exact queue proof");
    }'''
