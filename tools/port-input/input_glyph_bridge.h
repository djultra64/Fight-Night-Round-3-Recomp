// Private versioned host/GPU plugin ABI. Project work: djultra64.
#pragma once
#include <atomic>
#include <cstdint>
namespace fnr3::port {
inline constexpr uint32_t kGlyphBridgeVersion=1,kGlyphTextureBytes=16384,kGlyphPhysicalCount=14;
struct NativeGlyphRecord {
  const uint8_t* original; // Immutable, process lifetime; exact tiled bytes.
  uint64_t hash; // FNV-1a-64, followed by full memcmp before classification.
  int32_t action; // 0..13 guest action; -1 means non-remappable trigger.
  uint32_t pages[3][kGlyphPhysicalCount]; // Xbox, PlayStation, Switch; physical4Kpages.
};
struct NativeGlyphBridge {
  uint32_t version=kGlyphBridgeVersion,count=0;
  const NativeGlyphRecord* records=nullptr;
  std::atomic<uint64_t> controls{0}; // 14 physical indexes, packed4bits each; family atbit56.
  std::atomic<uint64_t> matches{0},switches{0}; // GPU integration evidence.
};
inline uint64_t GlyphHash(const uint8_t* p) {
  uint64_t h=14695981039346656037ull;
  for(unsigned i=0;i<kGlyphTextureBytes;++i){h^=p[i];h*=1099511628211ull;}return h;
}
}
#if defined(_WIN32)
#define FNR3_GLYPH_EXPORT __declspec(dllexport)
#else
#define FNR3_GLYPH_EXPORT __attribute__((visibility("default")))
#endif
#if defined(FNR3_GLYPH_BRIDGE_HOST)
extern "C" FNR3_GLYPH_EXPORT fnr3::port::NativeGlyphBridge* Fnr3GetInputGlyphBridge();
#endif
