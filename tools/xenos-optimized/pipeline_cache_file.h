// Project integration: djultra64. Driver cache files are local disposable data.
#pragma once
#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <span>
#include <string>
#include <vector>
#if defined(_WIN32)
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#endif

namespace fnr3::pipeline_cache {
constexpr size_t kMaxFileBytes = 64 * 1024 * 1024;
constexpr size_t kEnvelopeBytes = 48;
struct Identity {
  uint32_t vendor, device, driver;
  std::array<uint8_t, 16> uuid;
};
inline uint32_t Get32(std::span<const uint8_t> b, size_t at) {
  return uint32_t(b[at]) | uint32_t(b[at+1]) << 8 |
         uint32_t(b[at+2]) << 16 | uint32_t(b[at+3]) << 24;
}
inline void Put32(std::span<uint8_t> b, size_t at, uint32_t v) {
  for (size_t i=0; i<4; ++i) b[at+i] = uint8_t(v >> (8*i));
}
inline uint64_t Hash(std::span<const uint8_t> bytes) {
  uint64_t h = 14695981039346656037ull;
  for (auto b : bytes) h = (h ^ b) * 1099511628211ull;
  return h;
}
inline bool ValidPayload(std::span<const uint8_t> b, const Identity& id) {
  return b.size() >= 32 && b.size() <= kMaxFileBytes-kEnvelopeBytes &&
    Get32(b,0) >= 32 && Get32(b,0) <= b.size() && Get32(b,4) == 1 &&
    Get32(b,8) == id.vendor && Get32(b,12) == id.device &&
    std::equal(id.uuid.begin(),id.uuid.end(),b.begin()+16);
}
inline std::vector<uint8_t> Encode(std::span<const uint8_t> raw, const Identity& id) {
  if (!ValidPayload(raw,id)) return {};
  std::vector<uint8_t> b(kEnvelopeBytes+raw.size());
  constexpr std::array<uint8_t,8> magic{'F','N','R','P','C','0','0','1'};
  std::copy(magic.begin(),magic.end(),b.begin());
  Put32(b,8,id.vendor); Put32(b,12,id.device); Put32(b,16,id.driver);
  Put32(b,20,uint32_t(raw.size()));
  std::copy(id.uuid.begin(),id.uuid.end(),b.begin()+24);
  uint64_t hash=Hash(raw);
  for (size_t i=0;i<8;++i) b[40+i]=uint8_t(hash >> (8*i));
  std::copy(raw.begin(),raw.end(),b.begin()+kEnvelopeBytes);
  return b;
}
inline std::vector<uint8_t> Decode(std::span<const uint8_t> b, const Identity& id) {
  constexpr std::array<uint8_t,8> magic{'F','N','R','P','C','0','0','1'};
  if (b.size()<kEnvelopeBytes || b.size()>kMaxFileBytes ||
      !std::equal(magic.begin(),magic.end(),b.begin()) ||
      Get32(b,8)!=id.vendor || Get32(b,12)!=id.device || Get32(b,16)!=id.driver ||
      Get32(b,20)!=b.size()-kEnvelopeBytes ||
      !std::equal(id.uuid.begin(),id.uuid.end(),b.begin()+24)) return {};
  auto raw=b.subspan(kEnvelopeBytes);
  uint64_t stored=0;
  for (size_t i=0;i<8;++i) stored |= uint64_t(b[40+i]) << (8*i);
  if (!ValidPayload(raw,id) || Hash(raw)!=stored) return {};
  return {raw.begin(),raw.end()};
}
inline std::vector<uint8_t> Load(const std::filesystem::path& path, const Identity& id) {
  std::ifstream f(path,std::ios::binary|std::ios::ate);
  if (!f) return {};
  auto size=f.tellg();
  if (size<std::streamoff(kEnvelopeBytes) || size>std::streamoff(kMaxFileBytes)) return {};
  std::vector<uint8_t> b(static_cast<size_t>(size));
  f.seekg(0);
  if (!f.read(reinterpret_cast<char*>(b.data()),size)) return {};
  return Decode(b,id);
}
inline bool Save(const std::filesystem::path& path, std::span<const uint8_t> raw, const Identity& id) {
  auto b=Encode(raw,id);
  if (b.empty()) return false;
  static std::atomic<uint64_t> serial{0};
  auto tmp=path;
  tmp += ".tmp-" + std::to_string(std::chrono::steady_clock::now().time_since_epoch().count()) +
         "-" + std::to_string(serial.fetch_add(1));
  {
    std::ofstream f(tmp,std::ios::binary|std::ios::trunc);
    if (!f) return false;
    f.write(reinterpret_cast<const char*>(b.data()),std::streamsize(b.size()));
    f.flush();
    if (!f) { f.close(); std::error_code ec; std::filesystem::remove(tmp,ec); return false; }
  }
  std::error_code ec;
  // Replace within the same filesystem, keeping the old cache on failure.
#if defined(_WIN32)
  if (MoveFileExW(tmp.c_str(), path.c_str(), MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)) return true;
  ec = std::error_code(int(GetLastError()), std::system_category());
#else
  std::filesystem::rename(tmp,path,ec);
  if (!ec) return true;
#endif
  std::filesystem::remove(tmp,ec);
  return false;
}
}
