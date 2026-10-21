// Native APT actions connected to the host. Project work: djultra64.
#pragma once
#include "port_menu_queue.h"
#include <filesystem>
#include <memory>
namespace rex {class Runtime;namespace ui {class ImGuiDialog;class ImGuiDrawer;}}
namespace fnr3::port {
void InitializePortMenus(rex::Runtime&,std::shared_ptr<MenuQueue>,const std::filesystem::path& settings);
void ShutdownPortMenus();
bool PortMenuCallbacksRegistered();
std::unique_ptr<rex::ui::ImGuiDialog> CreateGraphicsDialog(
 rex::ui::ImGuiDrawer*,const std::filesystem::path& settings,
 std::function<void()> request_close);
} // namespace fnr3::port
