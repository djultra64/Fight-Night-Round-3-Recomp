// Real headless SDK VFS overlay contract. Project work: djultra64.
#ifdef NDEBUG
#undef NDEBUG
#endif
#include "port_frontend.h"
#include <cassert>
#include <iostream>
#include <memory>
#include <vector>
#include <rex/cvar.h>
#include <rex/filesystem/devices/host_path_device.h>
#include <rex/filesystem/file.h>
#include <rex/filesystem/vfs.h>

namespace {
std::vector<uint8_t> Read(rex::filesystem::Entry* entry) {
  assert(entry);
  rex::filesystem::File* file = nullptr;
  assert(entry->Open(rex::filesystem::FileAccess::kGenericRead, &file) == 0 && file);
  std::vector<uint8_t> bytes(entry->size());
  size_t count = 0;
  assert(file->ReadSync(bytes, 0, &count) == 0 && count == bytes.size());
  file->Destroy();
  return bytes;
}
std::vector<uint8_t> KernelRead(rex::filesystem::VirtualFileSystem& vfs,
    rex::filesystem::Entry* root, const std::string& path) {
  rex::filesystem::File* opened = nullptr;
  rex::filesystem::FileAction action{};
  assert(vfs.OpenFile(root, path, rex::filesystem::FileDisposition::kOpen,
      rex::filesystem::FileAccess::kGenericRead, false, true, &opened, &action) == 0);
  std::vector<uint8_t> bytes(opened->entry()->size());
  size_t count = 0;
  assert(opened->ReadSync(bytes, 0, &count) == 0 && count == bytes.size());
  opened->Destroy();
  return bytes;
}
std::vector<uint8_t> HostRead(const std::filesystem::path& path) {
  std::ifstream stream(path, std::ios::binary);
  return {std::istreambuf_iterator<char>(stream), std::istreambuf_iterator<char>()};
}
std::string Guest(std::string_view relative) {
  std::string result(relative);
  for (auto& ch : result) if (ch == '/') ch = '\\';
  return result;
}
}
int main(int argc, char** argv) {
  assert(argc == 3);  // game-data-root, prepared-overlay-root
  const std::filesystem::path game = argv[1], overlay = argv[2];
  rex::cvar::Init(argc, argv);
  rex::filesystem::VirtualFileSystem vfs;
  auto original = std::make_unique<rex::filesystem::HostPathDevice>("\\Device\\ContractGame", game, true);
  assert(original->Initialize());
  assert(vfs.RegisterDevice(std::move(original)));
  assert(vfs.RegisterSymbolicLink("game:", "\\Device\\ContractGame"));
  assert(vfs.RegisterSymbolicLink("d:", "\\Device\\ContractGame"));
  const auto unrelated = Read(vfs.ResolvePath("game:\\gui\\fn2k6\\main.big"));
  for (const auto& file : fnr3::port::kFrontendFiles)
    assert(Read(vfs.ResolvePath("game:\\" + Guest(file.relative))) == HostRead(game / file.relative));
  bool rejected = false;
  try { fnr3::port::MountFrontendFiles(vfs, game, overlay / "missing-contract-input"); }
  catch (const std::exception&) { rejected = true; }
  assert(rejected);
  for (const auto& file : fnr3::port::kFrontendFiles)
    assert(Read(vfs.ResolvePath("game:\\" + Guest(file.relative))) == HostRead(game / file.relative));
  fnr3::port::MountFrontendFiles(vfs, game, overlay);
  fnr3::port::MountFrontendFiles(vfs, game, overlay);  // idempotent; no alias cycle

  for (const auto& file : fnr3::port::kFrontendFiles) {
    const auto expected = HostRead(overlay / "assets" / file.relative);
    for (const auto& prefix : {"game:\\", "d:\\", "\\Device\\ContractGame\\", ""}) {
      auto* entry = vfs.ResolvePath(std::string(prefix) + Guest(file.relative));
      assert(entry && entry->is_read_only());
      assert(entry->absolute_path().starts_with("\\Device\\Fnr3Port\\assets\\"));
      assert(Read(entry) == expected);
      // Actual NtCreateFile path (parent resolution + GetChild), which the
      // earlier ResolvePath->Entry::Open contract did not exercise.
      assert(KernelRead(vfs, nullptr, std::string(prefix) + Guest(file.relative)) == expected);
    }
    const auto path = Guest(file.relative);
    auto* directory = vfs.ResolvePath("game:\\" + path.substr(0, path.find_last_of('\\')));
    assert(KernelRead(vfs, directory, path.substr(path.find_last_of('\\') + 1)) == expected);
  }
  for (const auto& file : fnr3::port::kFrontendSiblings) {
    const auto expected = HostRead(game / file.relative);
    assert(expected == HostRead(overlay / "assets" / file.relative));
    for (const auto& prefix : {"game:\\", "d:\\", "\\Device\\ContractGame\\", ""})
      assert(KernelRead(vfs, nullptr, std::string(prefix) + Guest(file.relative)) == expected);
  }
  // Retail code names the localization file with an uppercase extension.
  const auto locale_expected=HostRead(overlay / "assets/locale/ENGLISH.loc");
  assert(!locale_expected.empty());
  for(const auto& prefix:{"game:\\", "d:\\", "\\Device\\ContractGame\\"})
    assert(KernelRead(vfs,nullptr,std::string(prefix)+"locale\\ENGLISH.LOC")==locale_expected);
  assert(KernelRead(vfs, nullptr, "game:\\gui\\fn2k6\\main.big") == unrelated);
  assert(Read(vfs.ResolvePath("game:\\gui\\fn2k6\\main.big")) == unrelated);
  assert(Read(vfs.ResolvePath("d:\\gui\\fn2k6\\main.big")) == unrelated);
  std::cout << "PASS actual VFS OpenFile and root-relative opens, canonical parent aliases, both BIG overrides, all preserved siblings, readonly and unrelated resources\n";
}
