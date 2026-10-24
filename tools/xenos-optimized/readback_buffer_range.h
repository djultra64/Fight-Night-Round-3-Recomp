// Bounded shader addressing for scaled texture readback. Work: djultra64.
#pragma once
#include <cstdint>
#include <optional>
namespace fnr3::port {
struct ReadbackSourceRange {uint64_t offset,length;uint32_t shader_offset;};
inline std::optional<ReadbackSourceRange> ReadbackSourceBinding(uint64_t start,uint64_t length,uint64_t alignment,uint64_t buffer_size,uint64_t max_range) noexcept {
 if(!length||!alignment||(alignment&(alignment-1))||start>buffer_size||length>buffer_size-start)return std::nullopt;
 const uint64_t offset=start&~(alignment-1),relative=start-offset;
 if(relative>UINT32_MAX||relative>max_range||length>max_range-relative)return std::nullopt;
 return ReadbackSourceRange{offset,length+relative,uint32_t(relative)};
}
}
