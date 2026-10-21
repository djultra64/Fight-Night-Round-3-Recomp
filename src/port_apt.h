// Narrow original APT API adapter; no global no-op replacement. djultra64.
#pragma once
#include <cstdint>
#include <bit>
#include <cstring>
#include <stdexcept>
#include <optional>
#include <rex/ppc/context.h>
#include <rex/ppc/func.h>
namespace fnr3::port {
inline uint32_t ReadGuestWord(uint8_t* base,uint32_t address){uint32_t x;std::memcpy(&x,base+address,4);return std::byteswap(x);}
inline void WriteGuestWord(uint8_t* base,uint32_t address,uint32_t x){x=std::byteswap(x);std::memcpy(base+address,&x,4);}
struct AptApi {
 PPCFunc* allocate;PPCFunc* construct;PPCFunc* register_name;
 uint32_t allocator_global=0x8283D800,quit_global=0x82842F18;
 uint32_t function_vtable=0x820B5A98,original_noop=0x82391FA8;
};
// Native callback ABI: r3 is receiver, r4 is argument count. Values live on
// the APT operand stack; sub_82391F50(index) borrows an argument, sub_82399388
// converts it, and sub_823A2D28(int) creates a GC-managed integer result.
struct AptValueApi {
 PPCFunc* argument;PPCFunc* to_integer;PPCFunc* make_integer;
 uint32_t stack_global=0x8284C8D8;
};
inline std::optional<int32_t> ReadAptIntegerArgument(const PPCContext& incoming,
 uint8_t* base,const AptValueApi& api){
 if(incoming.r4.s32!=1||ReadGuestWord(base,api.stack_global)<1)return std::nullopt;
 PPCContext work=incoming;work.r3.u64=0;api.argument(work,base);
 const auto argument=work.r3.u32;
 if(!argument)return std::nullopt;
 const auto flags=ReadGuestWord(base,argument+4);
 if((flags&0x08000000)==0||(flags&0x7f)!=7)return std::nullopt;
 api.to_integer(work,base);return work.r3.s32;
}
inline void MakeAptIntegerResult(PPCContext& incoming,uint8_t* base,int32_t value,
 const AptValueApi& api){
 PPCContext work=incoming;work.r3.s64=value;api.make_integer(work,base);
 // The factory owns pooling and GC bookkeeping. Native getters return this
 // pointer directly without manually retaining or releasing the result.
 incoming.r3=work.r3;
}
inline uint32_t RegisterAptHostMethod(const PPCContext& incoming,uint8_t* base,
 uint32_t root,const AptApi& api,uint32_t thunk,uint32_t name){
 if(!root||!thunk||!name)throw std::runtime_error("Missing native menu service");
 PPCContext work=incoming;
 work.r3.u64=ReadGuestWord(base,api.allocator_global);work.r4.u64=36;
 if(!work.r3.u32)throw std::runtime_error("Missing native APT allocator");
 api.allocate(work,base);
 if(!work.r3.u32)throw std::runtime_error("Native menu allocation failed");
 work.r4.u64=thunk;api.construct(work,base);const auto object=work.r3.u32;
 if(!object)throw std::runtime_error("Native menu construction failed");
 work.r3.u64=root;work.r4.u64=name;work.r5.u64=object;
 api.register_name(work,base);return object;
}
inline void BindAptHostActions(PPCContext& returned,uint8_t* base,uint32_t root,
 const AptApi& api,uint32_t quit_thunk,uint32_t graphics_thunk,uint32_t graphics_name){
 if(!root||!quit_thunk||!graphics_thunk||!graphics_name)throw std::runtime_error("Missing native menu service");
 const auto quit=ReadGuestWord(base,api.quit_global);
 if(!quit||ReadGuestWord(base,quit)!=api.function_vtable)throw std::runtime_error("Unsupported native Quit object");
 const auto callback=ReadGuestWord(base,quit+32);
 if(callback!=api.original_noop&&callback!=quit_thunk)throw std::runtime_error("Unexpected native Quit callback");
 // Mutate only the specific Quit function object, preserving its identity and
 // refcount. Many unrelated script methods share the original no-op code.
 RegisterAptHostMethod(returned,base,root,api,graphics_thunk,graphics_name);
 WriteGuestWord(base,quit+32,quit_thunk);
 // Original return context remains untouched, including LR/nonvolatiles.
}
} // namespace fnr3::port
