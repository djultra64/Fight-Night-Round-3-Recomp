// Coherent native guest canvas, allocator ownership and UI. Work: djultra64.
#include "generated/default/fnr3_init.h"
#include "port_resolution.h"
#include "port_graphics.h"
#include <rex/cvar.h>
#include <rex/logging.h>
#include <algorithm>
#include <array>
#include <bit>
namespace {
const fnr3::port::Resolution& ActiveCanvas() {
  static const auto selected=[] {
    const auto id=rex::cvar::GetFlagByName("fnr3_resolution");
    for(const auto& p:fnr3::port::Resolutions()) if(p.id==id)return p;
    throw std::runtime_error("Unsupported native guest canvas");
  }();
  return selected;
}
}
extern "C" void __imp__sub_82269790(PPCContext&,uint8_t*);
extern "C" void sub_82269790(PPCContext& ctx,uint8_t* base) {
  __imp__sub_82269790(ctx,base);
  const auto& p=ActiveCanvas();
  REX_STORE_U32(0x82842B54,std::bit_cast<uint32_t>(float(p.GuestWidth())));
  REX_STORE_U32(0x82842B58,std::bit_cast<uint32_t>(float(p.GuestHeight())));
  REXLOG_INFO("FNR3: guest canvas {}x{}, scale {}, internal {}x{}",p.GuestWidth(),p.GuestHeight(),p.scale,p.width,p.height);
}
extern "C" void __imp__sub_8226DAE0(PPCContext&,uint8_t*);
extern "C" void sub_8226DAE0(PPCContext& ctx,uint8_t* base) {
  if(ActiveCanvas().ExtraGuestMemoryMiB()) {
    const uint32_t old=REX_LOAD_U32(0x827FCE80);
    if(old!=400u*1024*1024) rex::FatalError("Unexpected root budget in native canvas initialization");
    // The 512 MiB physical parent also serves allocations outside this root.
    // At 448 MiB the Pause menu's separate physical allocation fails; 400 MiB
    // cannot hold the enlarged category at 1080p. Keep 80 MiB outside the root
    // while preserving the category's full canvas budget below.
    const auto root_extra=std::min(32u,ActiveCanvas().ExtraGuestMemoryMiB());
    REX_STORE_U32(0x827FCE80,(400u+root_extra)*1024*1024);
    REXLOG_WARN("FNR3 root physical budget {} -> {} bytes",old,REX_LOAD_U32(0x827FCE80));
  }
  __imp__sub_8226DAE0(ctx,base);
}
extern "C" void __imp__sub_8226DEB0(PPCContext&,uint8_t*);
extern "C" void sub_8226DEB0(PPCContext& ctx,uint8_t* base) {
  if(ActiveCanvas().ExtraGuestMemoryMiB() && ctx.lr==0x8226D5C4) {
    const uint32_t old=REX_LOAD_U32(ctx.r3.u32+4);
    if(old!=244u*1024*1024) rex::FatalError("Unexpected category1 budget in native canvas initialization");
    REX_STORE_U32(ctx.r3.u32+4,(244u+ActiveCanvas().ExtraGuestMemoryMiB())*1024*1024);
    REXLOG_WARN("FNR3 category1 physical budget {} -> {} bytes",old,REX_LOAD_U32(ctx.r3.u32+4));
  }
  __imp__sub_8226DEB0(ctx,base);
}
extern "C" void __imp__sub_8251B4F8(PPCContext&,uint8_t*);
extern "C" void sub_8251B4F8(PPCContext& ctx,uint8_t* base) {
  const bool observe=ActiveCanvas().ExtraGuestMemoryMiB() && ctx.lr==0x8226DB64;
  const uint32_t size=ctx.r3.u32;
  __imp__sub_8251B4F8(ctx,base);
  if(observe) {
    REXLOG_WARN("FNR3 normal physical reservation bytes={} returned={:08X}",size,ctx.r3.u32);
    if(!ctx.r3.u32) rex::FatalError("Native canvas physical reservation failed; cannot use a different allocator owner");
  }
}


extern "C" void __imp__sub_82233578(PPCContext&,uint8_t*);
extern "C" void sub_82233578(PPCContext& ctx,uint8_t* base) {
  const uint32_t owner=ctx.r3.u32;
  __imp__sub_82233578(ctx,base);
  if(ActiveCanvas().GuestWidth()==1280 || !ctx.r3.u32) return;
  const uint32_t player=REX_LOAD_U32(owner+24),desc=REX_LOAD_U32(owner+80);
  if(!player||!desc)return;
  const uint32_t renderer=REX_LOAD_U32(player+148);
  if(!renderer)return;
  const uint32_t quad=REX_LOAD_U32(renderer+4),state=REX_LOAD_U32(renderer+76);
  const uint32_t mw=REX_LOAD_U32(player+96),mh=REX_LOAD_U32(player+100);
  const uint32_t tw=REX_LOAD_U32(desc+128),th=REX_LOAD_U32(desc+132);
  if(REX_LOAD_U32(player+176)>=5 || (state!=1&&state!=2)||!quad||!mw||!mh||!tw||!th) {
    REXLOG_WARN("FNR3 movie fit skipped player_state={} renderer_state={} quad={:08X} movie={}x{} target={}x{}",
      REX_LOAD_U32(player+176),state,quad,mw,mh,tw,th);return;
  }
  const float scale=std::min(float(tw)/float(mw),float(th)/float(mh));
  const float x=std::max(0.f,(float(tw)-float(mw)*scale)*.5f);
  const float y=std::max(0.f,(float(th)-float(mh)*scale)*.5f);
  const std::array<float,4> values{x,y,scale,scale};
  const std::array<uint32_t,4> p_offsets{76,80,88,92},r_offsets{52,56,64,68},methods{20,24,44,48};
  const PPCContext returned=ctx;
  for(size_t i=0;i<values.size();++i) {
    REX_STORE_U32(player+p_offsets[i],std::bit_cast<uint32_t>(values[i]));
    REX_STORE_U32(renderer+r_offsets[i],std::bit_cast<uint32_t>(values[i]));
    const uint32_t table=REX_LOAD_U32(quad);
    ctx=returned;ctx.r3.u64=quad;ctx.f1.f64=double(values[i]);ctx.ctr.u64=REX_LOAD_U32(table+methods[i]);
    REX_CALL_INDIRECT_FUNC(ctx.ctr.u32);
  }
  ctx=returned;
  REXLOG_WARN("FNR3 movie fit active movie={}x{} target={}x{} position={},{} scale={} quad={:08X} actual={},{},{},{}",
    mw,mh,tw,th,x,y,scale,quad,std::bit_cast<float>(REX_LOAD_U32(quad+60)),std::bit_cast<float>(REX_LOAD_U32(quad+64)),
    std::bit_cast<float>(REX_LOAD_U32(quad+72)),std::bit_cast<float>(REX_LOAD_U32(quad+76)));
}


namespace { thread_local uint32_t ui_primitive_depth=0; }
extern "C" void __imp__sub_821D51C8(PPCContext&,uint8_t*);
extern "C" void sub_821D51C8(PPCContext& ctx,uint8_t* base) {
  if(ActiveCanvas().GuestWidth()==1280){__imp__sub_821D51C8(ctx,base);return;}
  // This node owns its embedded UI primitive and draws it synchronously.
  struct Scope {Scope(){++ui_primitive_depth;} ~Scope(){--ui_primitive_depth;}} scope;
  __imp__sub_821D51C8(ctx,base);
}

// Scale primitives owned by the authored UI tree. Direct engine primitives
// (including transitions constructed with native dimensions) keep their units.
std::array<float, 2> Fnr3EnginePrimitiveScale(uint8_t* base) {
  if(!ui_primitive_depth) return {1.f,1.f};
  const uint32_t desc=REX_LOAD_U32(0x8280F24C);
  if(!desc || REX_LOAD_U32(desc+108)!=2) return {1.f,1.f};
  return {float(ActiveCanvas().GuestWidth())/1280.f,
          float(ActiveCanvas().GuestHeight())/720.f};
}

namespace { thread_local uint32_t engine_text_depth=0; }
extern "C" void __imp__sub_82237568(PPCContext&,uint8_t*);
extern "C" void sub_82237568(PPCContext& ctx,uint8_t* base) {
  if(ActiveCanvas().GuestWidth()==1280){__imp__sub_82237568(ctx,base);return;}
  struct Scope {Scope(){++engine_text_depth;} ~Scope(){--engine_text_depth;}} scope;
  __imp__sub_82237568(ctx,base);
}


void Fnr3ScaleEngineFontMatrix(PPCContext& ctx,uint8_t* base) {
  if(engine_text_depth && REX_LOAD_U8(ctx.r11.u32+92)!=3) {
    const uint32_t desc=REX_LOAD_U32(0x8280F24C);
    if(desc && REX_LOAD_U32(desc+108)==2) {
      const float sx=float(ActiveCanvas().GuestWidth())/1280.f;
      const float sy=float(ActiveCanvas().GuestHeight())/720.f;
      for(uint32_t row=0;row<4;++row) {
        const uint32_t x=ctx.r1.u32+80+row*16,y=x+4;
        REX_STORE_U32(x,std::bit_cast<uint32_t>(std::bit_cast<float>(REX_LOAD_U32(x))*sx));
        REX_STORE_U32(y,std::bit_cast<uint32_t>(std::bit_cast<float>(REX_LOAD_U32(y))*sy));
      }
    }
  }
}

void Fnr3DrawBloom(PPCContext& ctx,uint8_t* base,uint32_t texture) {
 const auto device=ctx.r3.u32;
 const auto type=REX_LOAD_U32(texture+36)&0x600u;
 const auto packed=REX_LOAD_U32(texture+24);
 const auto width=(packed&(type==0x400u?0x7ffu:0x1fffu))+1;
 const auto height=((packed>>(type==0x400u?11:13))&(type==0x400u?0x7ffu:0x1fffu))+1;
 if (type==0x400u || width>512 || height>512 || !width || !height) {
  sub_82379358(ctx,base); return;
 }
 const auto tl=REX_LOAD_U32(device+11524),br=REX_LOAD_U32(device+11528);
 const auto entry=ctx;
 ctx.r3.u64=device;ctx.r4.u64=0;ctx.r5.u64=0;ctx.r6.u64=width;ctx.r7.u64=height;
 sub_823703F8(ctx,base);
 ctx=entry;
 sub_82379358(ctx,base);
 const auto returned=ctx;
 ctx.r3.u64=device;ctx.r4.s64=int32_t(tl<<17)>>17;ctx.r5.s64=int32_t(tl<<1)>>17;
 ctx.r6.s64=int32_t(br<<17)>>17;ctx.r7.s64=int32_t(br<<1)>>17;
 sub_823703F8(ctx,base);
 ctx=returned;
}
