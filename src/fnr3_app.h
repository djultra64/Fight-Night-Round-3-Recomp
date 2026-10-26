// fnr3 - ReXGlue Recompiled Project
//
// Customize your app by overriding virtual hooks from rex::ReXApp.

#pragma once

#include "port_crash_diagnostics.h"
#include "port_graphics.h"
#include "port_frontend.h"
#include "port_input.h"
#include "port_menu.h"
#include "port_frame_times.h"
#include <rex/cvar.h>
#include <rex/ui/window.h>
#include <rex/ui/window_listener.h>
#include <rex/ui/imgui_dialog.h>
#include <rex/system/kernel_state.h>
#include <cstdlib>
#include <limits>
#include <rex/filesystem/entry.h>
#include <rex/filesystem/vfs.h>
#include <rex/logging.h>
#include <rex/rex_app.h>
#include <rex/runtime.h>
#include <rex/system/gpu_plugin.h>

class Fnr3App : public rex::ReXApp {
public:
  using rex::ReXApp::ReXApp;
  ~Fnr3App() override {
    std::string error;
    if (!fnr3::port::FlushFrameTimes(&error))
      REXLOG_ERROR("FNR3: frame trace could not be saved: {}", error);
  }

  static std::unique_ptr<rex::ui::WindowedApp>
  Create(rex::ui::WindowedAppContext &ctx) {
    return std::unique_ptr<Fnr3App>(new Fnr3App(ctx, "Fight Night Round 3 Recomp v1.0.2", PPCImageConfig));
  }

  // Override virtual hooks for customization:
  void OnPostInitLogging() override {
    REXLOG_INFO("FNR3: startup diagnostics; build 1.0.2 + stability candidate, work djultra64");
#if defined(_WIN32)
    // The launcher passes a distinct directory for every diagnostic attempt.
    if (const wchar_t* directory = _wgetenv(L"FNR3_DIAGNOSTICS_DIR")) {
      std::string error;
      try {
        if (!fnr3::port::InstallCrashDiagnostics(directory, &error))
          REXLOG_WARN("FNR3: crash diagnostics unavailable: {}", error);
        else
          REXLOG_INFO("FNR3: Windows unhandled-crash diagnostics enabled");
      } catch (const std::exception& e) {
        REXLOG_WARN("FNR3: crash diagnostics unavailable: {}", e.what());
      }
    }
#endif
  }
  void OnPreSetup(rex::RuntimeConfig &config) override {
    if (config.gpu_plugin.empty()) {
      config.gpu_plugin = "xenos";
    }
    if (config.gpu_plugin == "xenos") {
      // Register backend settings before applying the unified profile; device
      // creation still belongs to ReXApp. Leave load errors to its normal path.
      if (!config.graphics)
        config.graphics = rex::system::LoadGpuPlugin(config.gpu_plugin,
                                                   "vulkan"
        );
      if (config.graphics)
        fnr3::port::ApplyGraphicsSettings();
    }
  }
  // void OnLoadXexImage(std::string& xex_image) override {}
  // void OnPostLoadXexImage() override {}
  // Retail code opens these shaders by basename. The SDK VFS has no guest
  // current-directory support; map them to their original on-disc entries.
  void OnPreLaunchModule() override {
    auto *vfs = runtime()->file_system();
    auto *shaders = vfs->ResolvePath("d:\\render\\shaders");
    if (!shaders) {
      REXLOG_ERROR("FNR3: original shader directory is unavailable");
      return;
    }
    size_t count = 0;
    for (const auto &entry : shaders->children()) {
      if (entry->name().ends_with(".fxo")) {
        vfs->RegisterSymbolicLink(entry->name(), entry->absolute_path());
        ++count;
      }
    }
    REXLOG_INFO("FNR3: mapped {} original shader basenames", count);
  }
  // void OnCreateDialogs(rex::ui::ImGuiDrawer* drawer) override {}
  // std::unique_ptr<rex::ui::ImGuiDialog> CreateAchievementsOverlay() override;
  // std::unique_ptr<rex::ui::AchievementNotificationDialog>
  // CreateAchievementNotificationDialog() override;
  void OnConfigurePaths(rex::PathConfig& paths) override {
    paths.config_path=paths.user_data_root / "port-settings.toml";
    settings_path_=paths.config_path;
  }
  void OnPostSetup() override { fnr3::port::InitializeInputPrompts(); }
  void OnCreateDialogs(rex::ui::ImGuiDrawer*) override {
    window()->AddInputListener(&keyboard_, std::numeric_limits<size_t>::max());
    keyboard_registered_=true;
  }
  void LaunchModule() override {
    try {
      const auto frontend=ResourceRoot("fnr3_frontend_root","port-overrides");
      const auto glyphs=ResourceRoot("fnr3_glyph_root","input-glyphs");
      fnr3::port::MountFrontendFiles(*runtime()->file_system(),game_data_root(),frontend);
      auto* context=&app_context();
      queue_=fnr3::port::MenuQueue::Create(
        [context](std::function<void()> fn){return context->CallInUIThreadDeferred(std::move(fn));},
        [this](fnr3::port::MenuAction action){
          if(action==fnr3::port::MenuAction::Restart){exit_status_=42;window()->RequestClose();return;}
          if(action==fnr3::port::MenuAction::Quit){exit_status_=0;window()->RequestClose();return;}

        });
      fnr3::port::InitializePortMenus(*runtime(),queue_,settings_path_);
      if(!fnr3::port::InitializeNativeInputGlyphs(runtime()->memory(),glyphs))
        throw std::runtime_error("Prepared controller glyphs are missing or incompatible");
      fnr3::port::FrameTimeOptions trace;
      trace.output=rex::cvar::GetFlagByName("fnr3_frame_trace");
      trace.cache_state=rex::cvar::GetFlagByName("fnr3_trace_cache");
      trace.scene=rex::cvar::GetFlagByName("fnr3_trace_scene");
      std::string error;
      if(!fnr3::port::InitializeFrameTimes(trace,&error))throw std::runtime_error(error);
    }catch(const std::exception& e){
      REXLOG_ERROR("FNR3: port preflight failed: {}",e.what());
      rex::ui::ImGuiDialog::ShowMessageBox(imgui_drawer(),"Port setup failed",e.what());
      return; // No guest launch after a failed preflight.
    }
    rex::ReXApp::LaunchModule();
  }
  // The repaired SDK intentionally hard-exits after terminating the title:
  // subsystem destruction can deadlock on a surviving guest lock owner. Do
  // application cleanup and stop/flush tracing explicitly before that exit.
  void OnClosing(rex::ui::UIEvent&) override {
    ui_alive_->store(false);
    if(queue_)queue_->Shutdown();
    fnr3::port::ShutdownPortMenus();
    if(runtime() && runtime()->kernel_state())runtime()->kernel_state()->TerminateTitle();
    OnShutdown();
    std::string error;
    if(!fnr3::port::FlushFrameTimes(&error))REXLOG_ERROR("FNR3: frame trace save failed: {}",error);
    REXLOG_INFO("FNR3: title closed through port shutdown (exit {})",exit_status_);
    rex::FlushLogging();
    std::_Exit(exit_status_);
  }
  void OnShutdown() override {
    ui_alive_->store(false);
    if(queue_)queue_->Shutdown();
    fnr3::port::ShutdownPortMenus();
    if(keyboard_registered_ && window())window()->RemoveInputListener(&keyboard_);
    keyboard_registered_=false;
    fnr3::port::ShutdownInputPrompts();
    const auto stats=fnr3::port::GetNativeGlyphStats();
    REXLOG_INFO("FNR3: native glyph matches {}, control switches {}",stats.matches,stats.switches);
    queue_.reset();
  }
private:
  class KeyboardObserver final : public rex::ui::WindowInputListener {
    void OnKeyDown(rex::ui::KeyEvent&) override {fnr3::port::NotifyKeyboardInput();}
    void OnMouseDown(rex::ui::MouseEvent&) override {fnr3::port::NotifyKeyboardInput();}
  } keyboard_;
  std::filesystem::path ResourceRoot(const char* flag,const char* folder) const {
    const auto configured=rex::cvar::GetFlagByName(flag);
    return configured.empty()?game_data_root().parent_path()/"runtime"/folder:std::filesystem::path(configured);
  }
  std::filesystem::path settings_path_;
  std::shared_ptr<fnr3::port::MenuQueue> queue_;
  std::shared_ptr<std::atomic<bool>> ui_alive_=std::make_shared<std::atomic<bool>>(true);
  int exit_status_=0;
  bool keyboard_registered_=false;
};
