// Project work: djultra64. Captured input packets remain private.
// Runs the actual Windows runtime decoder; no audio-device or GPU dependency.
#include <rex/audio/xma/context.h>
#include <rex/cvar.h>
#include <rex/system/xmemory.h>
#include <array>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <string_view>
#include <vector>

struct Result {
  std::vector<uint8_t> pcm;
  unsigned error = 0;
  bool full_ring_changed = false;
};

Result Decode(const std::array<std::array<uint8_t, 2048>, 2>& packets,
              unsigned ring_blocks, bool late, bool pause_consumer,
              bool reuse_released_input, bool reset_stream, bool wait_with_old_refill,
              bool loop) {
  rex::memory::Memory memory;
  if (!memory.Initialize()) throw "memory initialization failed";
  auto alloc = [&](unsigned n) {
    return memory.SystemHeapAlloc(n, 256, rex::memory::kSystemHeapPhysical);
  };
  const auto context_address = alloc(64), input0 = alloc(2048), input1 = alloc(2048);
  const auto output = alloc(ring_blocks * 256);
  if (!context_address || !input0 || !input1 || !output) throw "allocation failed";
  std::memcpy(memory.TranslateVirtual(input0), packets[0].data(), 2048);
  std::memcpy(memory.TranslateVirtual(input1), packets[1].data(), 2048);
  auto* raw = memory.TranslateVirtual(context_address);
  std::memset(raw, 0, 64);
  rex::audio::XMA_CONTEXT_DATA data(raw);
  data.input_buffer_0_ptr = memory.GetPhysicalAddress(input0);
  data.input_buffer_1_ptr = memory.GetPhysicalAddress(input1);
  data.output_buffer_ptr = memory.GetPhysicalAddress(output);
  data.input_buffer_0_packet_count = data.input_buffer_1_packet_count = 1;
  data.input_buffer_0_valid = 1;
  data.input_buffer_1_valid = !late;
  data.output_buffer_valid = 1;
  data.output_buffer_block_count = ring_blocks;
  data.subframe_decode_count = 4;
  data.sample_rate = 2;
  data.is_stereo = 1;
  data.input_buffer_read_offset = 32;
  if (loop) {
    const unsigned first = 32 + (((packets[0][0] & 3) << 13) |
                                (packets[0][1] << 5) | (packets[0][2] >> 3));
    unsigned size = 0;
    for (unsigned i = 0; i < 15; ++i)
      size = size * 2 + ((packets[0][(first + i) / 8] >> (7 - (first + i) % 8)) & 1);
    if (size != 3229 && size != 3550) throw "unknown captured loop fixture";
    data.loop_start = first;
    data.loop_end = first == 48 ? (size == 3229 ? 14185 : 13235) :
                                 (size == 3229 ? 16381 : 16377);
    data.loop_subframe_end = 3;
    data.loop_count = 1;
  }
  data.Store(raw);
  rex::audio::XmaContext context;
  if (context.Setup(0, &memory, context_address)) throw "decoder setup failed";
  context.set_is_allocated(true);
  Result result;
  unsigned last_write = 0, quiet = 0;
  bool delivered = !late;
  auto* pcm = memory.TranslateVirtual(output);
  for (unsigned iteration = 0; iteration < 256; ++iteration) {
    context.Enable();
    context.Work();
    rex::audio::XMA_CONTEXT_DATA current(raw);
    const unsigned write = current.output_buffer_write_offset;
    if (current.error_status) {
      result.error = current.error_status;
      std::fprintf(stderr, "decoder error %u, iteration %u, offset %u, valid %u/%u\n",
                   result.error, iteration, unsigned(current.input_buffer_read_offset),
                   unsigned(current.input_buffer_0_valid), unsigned(current.input_buffer_1_valid));
      break;
    }
    if (pause_consumer && iteration == 0) {
      // No consumer acknowledgement: the following Work must return without
      // overwriting pending PCM. Preserve the entire ring as well as its cursor.
      std::vector<uint8_t> saved(pcm, pcm + ring_blocks * 256);
      context.Enable();
      context.Work();
      rex::audio::XMA_CONTEXT_DATA full(raw);
      result.full_ring_changed = full.output_buffer_write_offset != write ||
          full.error_status || std::memcmp(saved.data(), pcm, saved.size());
      if (result.full_ring_changed) break;
    }
    const unsigned blocks = (write + ring_blocks - last_write) % ring_blocks;
    for (unsigned b = 0; b < blocks; ++b) {
      const auto* first = pcm + ((last_write + b) % ring_blocks) * 256;
      result.pcm.insert(result.pcm.end(), first, first + 256);
    }
    last_write = write;
    quiet = blocks ? 0 : quiet + 1;
    current.output_buffer_read_offset = write;
    current.output_buffer_valid = 1;
    // Deliver a continuation after the decoder has consumed the first packet.
    // A temporarily missing successor must not discard the split frame.
    if (!delivered && !current.input_buffer_0_valid && reset_stream) {
      context.Clear();
      data.input_buffer_0_valid = data.input_buffer_1_valid = 1;
      data.Store(raw);
      result.pcm.clear();
      last_write = quiet = 0;
      delivered = true;
      continue;
    }
    if (!delivered && (!current.input_buffer_0_valid ||
                      (!reuse_released_input && quiet))) {
      if (reuse_released_input) {
        // The valid bit handed ownership back to the guest. Any retained
        // fragment must survive immediate reuse of the original packet bytes.
        std::memset(memory.TranslateVirtual(input0), 0xD5, 2048);
      }
      if (wait_with_old_refill) {
        current.input_buffer_0_valid = 1;
        current.Store(raw);
        for (unsigned retry = 0; retry < 3; ++retry) {
          context.Enable();
          context.Work();
          rex::audio::XMA_CONTEXT_DATA waiting(raw);
          result.full_ring_changed |= waiting.output_buffer_write_offset != write ||
              waiting.error_status || waiting.current_buffer != 1 ||
              !waiting.input_buffer_0_valid || waiting.input_buffer_1_valid;
        }
        if (result.full_ring_changed) break;
        current = rex::audio::XMA_CONTEXT_DATA(raw);
        // Withdraw the unconsumed future buffer from this bounded testcase.
        current.input_buffer_0_valid = 0;
      }
      current.input_buffer_1_valid = 1;
      delivered = true;
      quiet = 0;
    }
    current.Store(raw);
    if (delivered && quiet >= 3) break;
  }
  return result;
}

// Move the packet boundary from a split length header into the preceding
// frame's body. The captured XMA1 streams have 3 or 7 remaining header bits;
// inserting 16 padding bits before frame 0 preserves the encoded frame bits.
// Packet headers, next-frame-in-packet flags and trailing padding change.
void SplitBody(std::array<std::array<uint8_t, 2048>, 2>& packets) {
  auto bit = [&](unsigned offset) {
    return (packets[0][offset / 8] >> (7 - offset % 8)) & 1;
  };
  unsigned end = 32;
  while (16384 - end >= 15) {
    unsigned size = 0;
    for (unsigned i = 0; i < 15; ++i) size = size * 2 + bit(end + i);
    if (!size || size == 32767 || size > 16384 - end) throw "unexpected capture frame";
    if (!bit(end + size - 1)) throw "capture has no split header";
    end += size;
  }
  if (end != 16381 && end != 16377) throw "unexpected capture tail";
  auto original = packets;
  constexpr unsigned payload_bits = 2044 * 8;
  for (unsigned i = 0; i < payload_bits * 2; ++i) {
    unsigned value = 0;
    if (i >= 16) {
      unsigned from = i - 16;
      value = (original[from / payload_bits][4 + (from % payload_bits) / 8] >>
               (7 - from % 8)) & 1;
    }
    auto& byte = packets[i / payload_bits][4 + (i % payload_bits) / 8];
    const auto mask = uint8_t(1u << (7 - i % 8));
    byte = uint8_t((byte & ~mask) | (value ? mask : 0));
  }
  auto first = [&](unsigned packet, unsigned offset) {
    unsigned value = offset - 32;
    packets[packet][0] = uint8_t((packets[packet][0] & 0xFC) | (value >> 13));
    packets[packet][1] = uint8_t(value >> 5);
    packets[packet][2] = uint8_t((packets[packet][2] & 7) | ((value & 31) << 3));
  };
  first(0, 48);
  first(1, 32 + end + 16 - 16384);  // 45 or 41, independently checked boundaries.
  auto flag = [&](unsigned offset, bool next) {
    auto& byte = packets[1][offset / 8];
    const auto mask = uint8_t(1u << (7 - offset % 8));
    byte = uint8_t((byte & ~mask) | (next ? mask : 0));
  };
  // The preceding frame is now the last one that began in packet0; the
  // formerly split-header frame now begins in packet1 and has successors there.
  flag(32 + end + 16 - 16384 - 1, false);  // bit44 or40.
  const unsigned old_first = 32 + (((original[1][0] & 3) << 13) |
                                   (original[1][1] << 5) | (original[1][2] >> 3));
  flag(old_first + 16 - 1, true);  // bit2123 or3101.
}

int main(int argc, char** argv) {
  if (argc != 4 && argc != 5) return 2;
  std::array<std::array<uint8_t, 2048>, 2> packets;
  for (unsigned i = 0; i < 2; ++i) {
    std::ifstream input(argv[i + 1], std::ios::binary);
    input.read(reinterpret_cast<char*>(packets[i].data()), packets[i].size());
    if (input.gcount() != packets[i].size()) return 3;
  }
  const bool legacy = argc == 5 && std::string_view(argv[4]) == "legacy";
  if (argc == 5 && !legacy) return 2;
  rex::cvar::SetFlagByName("fnr3_xma_no_lookahead", legacy ? "false" : "true");
  const std::string_view mode = argv[3];
  if (mode != "reference" && mode != "ring7" && mode != "ring13" &&
      mode != "late" && mode != "full" && mode != "late_reuse" &&
      mode != "late_reset" && mode != "body_late" && mode != "body_reuse" &&
      mode != "late_wait" && mode != "body_wait" &&
      mode != "loop_late" && mode != "loop_body" &&
      mode != "tail_early" && mode != "tail_late" && mode != "tail_reuse" &&
      mode != "tail_body_early" && mode != "tail_body_late" &&
      mode != "tail_body_reuse") return 2;
  try {
    const bool body = mode.starts_with("body_") || mode == "loop_body" ||
                      mode.starts_with("tail_body_");
    const bool loop = mode.starts_with("loop_");
    const bool tail = mode.starts_with("tail_");
    if (body) SplitBody(packets);
    if (tail) {
      // This final packet carries only continuation bits: no frame begins here.
      packets[1][0] |= 3;
      packets[1][1] = 0xFF;
      packets[1][2] |= 0xF8;  // first-new offset32799, beyond the packet.
      packets[1][3] = 0xFF;  // No new frame starts in this packet.
    }
    const auto reference = Decode(packets, 31, false, false, false, false, false, loop);
    // Independent counts for the two known captures: 10 frames, plus a loop
    // through the last frame beginning in packet0 (7/6, or6/5 after repacking).
    const unsigned first_length = ((unsigned(packets[0][body ? 6 : 4]) << 8) |
                                   packets[0][body ? 7 : 5]) >> 1;
    const unsigned extra = loop ? (first_length == 3229 ? 7 : 6) - unsigned(body) : 0;
    const unsigned frames = tail ? (first_length == 3229 ? 7 : 6) - unsigned(body) : 10;
    const unsigned expected = (frames + extra - unsigned(legacy)) * 2048;
    if (reference.error || reference.pcm.size() != expected) {
      std::fprintf(stderr, "reference failed: %zu bytes, error %u\n",
                   reference.pcm.size(), reference.error);
      return 1;
    }
    const unsigned blocks = mode == "ring7" || mode == "full" ? 7 :
                            mode == "ring13" ? 13 : 31;
    const bool late = mode.starts_with("late") || mode.starts_with("body_") || loop ||
                      (tail && !mode.ends_with("early"));
    const auto actual = Decode(packets, blocks, late, mode == "full",
                               mode.ends_with("reuse") || mode.ends_with("wait"),
                               mode == "late_reset", mode.ends_with("wait"), loop);
    std::printf("mode=%s legacy=%u ring=%u expected_bytes=%u actual_bytes=%zu error=%u\n",
                 argv[3], legacy, blocks, expected, actual.pcm.size(), actual.error);
    if (actual.error || actual.full_ring_changed || actual.pcm != reference.pcm) {
      std::fputs("FAIL: decoded PCM lost, reordered, overwritten or terminated\n", stderr);
      return 1;
    }
    std::puts("PASS: complete PCM matches reference byte for byte");
  } catch (const char* message) {
    std::fprintf(stderr, "infrastructure error: %s\n", message);
    return 4;
  }
}
