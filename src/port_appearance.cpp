// Read GPU hair-color bakes before the original CPU BC3 compressor consumes them.
// Project work: djultra64.
#include "port_appearance.h"
#include <rex/ppc/context.h>
#include <rex/logging.h>
extern "C" void __imp__sub_8220B570(PPCContext&,uint8_t*);
extern "C" void __imp__sub_822412A0(PPCContext&,uint8_t*);
extern "C" void __imp__sub_8236ECD0(PPCContext&,uint8_t*);
namespace {
fnr3::port::TextureBakeReadbacks readbacks;
thread_local uint64_t current_bake=0;
thread_local bool hair_composite=false;
struct CompositeScope {
 bool previous=hair_composite;
 explicit CompositeScope(bool enabled){hair_composite=enabled;}
 ~CompositeScope(){hair_composite=previous;}
};
struct HairBakeScope {
 uint64_t previous=current_bake,owner=readbacks.Begin();
 HairBakeScope(){current_bake=owner;}
 ~HairBakeScope(){readbacks.End(owner);current_bake=previous;}
};
uint32_t GuestWord(const uint8_t* p){
 return ((uint32_t(p[0])<<24)|(uint32_t(p[1])<<16)|(uint32_t(p[2])<<8)|p[3]);
}
}
#if defined(_WIN32)
#define FNR3_BAKE_EXPORT __declspec(dllexport)
#else
#define FNR3_BAKE_EXPORT __attribute__((visibility("default")))
#endif
extern "C" FNR3_BAKE_EXPORT bool Fnr3ConsumeTextureBakeReadback(uint32_t address,uint32_t length){
 return readbacks.Consume(address,length);
}
extern "C" void sub_8220B570(PPCContext& ctx,uint8_t* base){
 // Keep requests alive through the subsequent original CPU compression, which
 // waits for the GPU resolve. Scope cleanup also handles skipped/failed draws.
 HairBakeScope scope;
 __imp__sub_8220B570(ctx,base);
}
extern "C" void sub_822412A0(PPCContext& ctx,uint8_t* base){
 CompositeScope scope(current_bake&&fnr3::port::IsHairCompositeCaller(ctx.lr));
 if(hair_composite&&ctx.r3.u32){
  // Mip zero bypasses the original mip-layout helper. Later mips, including
  // packed sub-page tails, register their exact destinations in that helper.
  const uint32_t address=fnr3::port::HairResolvePhysicalAddress(GuestWord(base+ctx.r3.u32+20)&0xFFFFF000u);
  readbacks.Request(current_bake,address);
  REXLOG_INFO("FNR3: hair texture bake mip 0 readback target {:08X}",address);
 }
 __imp__sub_822412A0(ctx,base);
}
extern "C" void sub_8236ECD0(PPCContext& ctx,uint8_t* base){
 const bool capture=current_bake&&hair_composite&&ctx.lr==0x8237C5F8;
 const uint32_t output=capture?GuestWord(base+ctx.r1.u32+100):0;
 __imp__sub_8236ECD0(ctx,base);
 if(output){
  const uint32_t address=fnr3::port::HairResolvePhysicalAddress(GuestWord(base+output));
  readbacks.Request(current_bake,address);
  REXLOG_INFO("FNR3: hair texture bake mip readback target {:08X}",address);
 }
}
