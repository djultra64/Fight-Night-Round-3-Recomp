// Guest scheduling hooks. Project work: djultra64.
#pragma once
#include <cstdint>
#include "port_timing_policy.h"
extern "C" {
void Fnr3Native60Begin(uint8_t* base) noexcept;
void Fnr3Native60End(uint8_t* base) noexcept;
void Fnr3ReplaySequenceBegin(uint8_t* base, uint32_t parent) noexcept;
void Fnr3ReplaySequenceEnd(uint8_t* base) noexcept;
void Fnr3ReplayPhaseEnd(uint8_t* base) noexcept;
float Fnr3ReplayTickScale(uint8_t* base) noexcept;
uint32_t Fnr3ReplayCountdown(uint32_t object, uint32_t current, float scale) noexcept;
}
