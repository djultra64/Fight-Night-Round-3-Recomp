// Native frontend VFS overlays. Project work: djultra64.
#include "port_frontend.h"
#include <algorithm>
#include <memory>
#include <string>
#include <utility>
#include <vector>
#include <rex/filesystem/devices/host_path_device.h>
#include <rex/filesystem/entry.h>
#include <rex/filesystem/vfs.h>

namespace fnr3::port {
namespace {
constexpr std::string_view kMountPath = "\\Device\\Fnr3Port";
std::string GuestPath(std::string_view path) {
  std::string result(path);
  std::replace(result.begin(), result.end(), '/', '\\');
  return result;
}
}
void MountFrontendFiles(rex::filesystem::VirtualFileSystem& vfs,
                        const std::filesystem::path& game_data,
                        const std::filesystem::path& overlay) {
  // Validate every source/output before touching the guest filesystem.
  ValidateFrontendFiles(game_data, overlay);
  std::vector<std::pair<std::string, std::string>> aliases;
  size_t already_mounted = 0;
  for (const auto& file : kFrontendFiles) {
    const std::string relative = GuestPath(file.relative);
    const std::string target = std::string(kMountPath) + "\\assets\\" + relative;
    // Full game:/d: aliases compete with the generic device links in an
    // unordered prefix map. NtCreateFile/OpenFile resolves a parent directory
    // then GetChild(filename), so a full-file alias alone is bypassed. Bind
    // the canonical parent to a complete, verified read-only sibling set.
    auto* original = vfs.ResolvePath("game:\\" + relative);
    if (!original) original = vfs.ResolvePath("d:\\" + relative);
    if (!original) throw std::runtime_error("Cannot resolve original native frontend: " + relative);
    if (original->absolute_path() == target && original->is_read_only()) {
      ++already_mounted;
      continue;
    }
    const auto original_parent = original->absolute_path().substr(0, original->absolute_path().find_last_of('\\'));
    const auto relative_parent = relative.substr(0, relative.find_last_of('\\'));
    const auto target_parent = target.substr(0, target.find_last_of('\\'));
    aliases.emplace_back(original_parent, target_parent);
    // Some callers use relative paths without a drive alias.
    aliases.emplace_back(relative_parent, target_parent);
  }
  if (already_mounted == kFrontendFiles.size()) return;
  if (already_mounted) throw std::runtime_error("Native frontend overlay is only partially mounted");
  auto device = std::make_unique<rex::filesystem::HostPathDevice>(kMountPath, overlay, true);
  if (!device->Initialize()) throw std::runtime_error("Cannot initialize read-only native frontend overlay");
  // Fail before registration if either verified file cannot be represented by
  // the host filesystem device (including case/path handling on this platform).
  for (const auto& file : kFrontendFiles) {
    auto* entry = device->ResolvePath("assets\\" + GuestPath(file.relative));
    if (!entry || !entry->is_read_only())
      throw std::runtime_error("Prepared native frontend is unavailable on overlay device");
  }
  if (!vfs.RegisterDevice(std::move(device)))
    throw std::runtime_error("Cannot register native frontend overlay device");
  for (const auto& [path, target] : aliases) {
    if (!vfs.RegisterSymbolicLink(path, target))
      throw std::runtime_error("Cannot bind native frontend overlay: " + path);
  }
}
}  // namespace fnr3::port
