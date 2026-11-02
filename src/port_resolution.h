// Native canvas and presentation hooks. Project work: djultra64.
#pragma once
#include <rex/ppc/context.h>
#include <cstdint>
#include <array>
std::array<float, 2> Fnr3EnginePrimitiveScale(uint8_t* base);
void Fnr3ScaleEngineFontMatrix(PPCContext& ctx, uint8_t* base);
void Fnr3DrawBloom(PPCContext& ctx, uint8_t* base, uint32_t texture);
