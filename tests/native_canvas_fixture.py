"""Compile the real project canvas hooks against observed API boundaries. djultra64."""
from pathlib import Path

CONTEXT = r'''
#pragma once
#include <cstdint>
union PPCRegister { uint64_t u64=0; int64_t s64; uint32_t u32; int32_t s32; double f64; };
struct PPCContext { PPCRegister r1,r3,r4,r5,r6,r7,r11,f1,ctr; uint64_t lr=0; uint64_t preserved[32]{}; };
'''
INIT = r'''
#pragma once
#include <rex/ppc/context.h>
#include <cstdint>
uint32_t Read32(uint32_t); uint8_t Read8(uint32_t); void Write32(uint32_t,uint32_t);
void FakeIndirect(PPCContext&,uint8_t*,uint32_t);
#define REX_LOAD_U32(a) Read32(uint32_t(a))
#define REX_LOAD_U8(a) Read8(uint32_t(a))
#define REX_STORE_U32(a,v) Write32(uint32_t(a),uint32_t(v))
#define REX_CALL_INDIRECT_FUNC(a) FakeIndirect(ctx,base,a)
void sub_82379358(PPCContext&,uint8_t*); void sub_823703F8(PPCContext&,uint8_t*);
'''
HARNESS = r'''
#include <cassert>
#include <cstring>
#include <iostream>
#include <string>
#include <vector>
#include <unordered_map>
#include <stdexcept>
#include <bit>
#include <cmath>
#include "generated/default/fnr3_init.h"
std::unordered_map<uint32_t,uint8_t> memory;
std::string resolution="1080p",mode;
uint32_t Read32(uint32_t a){uint32_t v=0;for(int i=0;i<4;++i)v=(v<<8)|memory[a+i];return v;}
uint8_t Read8(uint32_t a){return memory[a];}
void Write32(uint32_t a,uint32_t v){for(int i=3;i>=0;--i){memory[a+i]=v&255;v>>=8;}}
namespace rex::cvar { std::string GetFlagByName(const char*) {return resolution;} }
namespace rex { [[noreturn]] void FatalError(const char* text){std::cerr<<text<<"\n";std::exit(73);} }
#include "PRODUCTION_CPP"
void Check(bool b,const char* why){if(!b)throw std::runtime_error(why);}
bool Equal(const PPCContext& a,const PPCContext& b){return std::memcmp(&a,&b,sizeof(a))==0;}
PPCContext Pattern(uint64_t n){PPCContext c{};c.r1.u64=0x3000;c.r3.u64=0x10000;c.r4.u64=42;c.r5.u64=43;c.r6.u64=44;c.r7.u64=45;c.r11.u64=0x2000;c.f1.f64=3.25;c.lr=17;c.ctr.u64=29;for(unsigned i=0;i<32;++i)c.preserved[i]=n+i;return c;}
PPCContext expected,returned;unsigned draws=0,physical_calls=0,root_calls=0,child_calls=0;
struct Rect {int64_t x,y,w,h;};std::vector<Rect> rects;std::vector<double> setters;unsigned font_level=0;
void sub_823703F8(PPCContext& c,uint8_t*){rects.push_back({c.r4.s64,c.r5.s64,c.r6.s64,c.r7.s64});Write32(0x10000,Read32(0x10000)+16);c=Pattern(500);}
void sub_82379358(PPCContext& c,uint8_t*){Check(Equal(c,expected),"draw arguments changed");++draws;Write32(0x10000,Read32(0x10000)+24);c=returned;}
void FakeIndirect(PPCContext& c,uint8_t*,uint32_t a){Check(a==0x9000+setters.size(),"movie setter order");Check(c.r3.u32==0x5000,"movie quad receiver");setters.push_back(c.f1.f64);c=Pattern(900);}
extern "C" void __imp__sub_82269790(PPCContext&,uint8_t*){}
extern "C" void __imp__sub_8226DAE0(PPCContext&,uint8_t*){++root_calls;}
extern "C" void __imp__sub_8226DEB0(PPCContext&,uint8_t*){++child_calls;}
extern "C" void __imp__sub_8251B4F8(PPCContext& c,uint8_t*){++physical_calls;if(mode=="physical_null")std::cout<<"PHYSICAL_ORIGINAL\n";c.r3.u64=mode=="physical_null"?0:0xC3000000;}
extern "C" void __imp__sub_82233578(PPCContext& c,uint8_t*){c=returned;}
std::array<float,2> primitive_scale{1.f,1.f};unsigned primitive_level=0;
extern "C" void __imp__sub_821D51C8(PPCContext& c,uint8_t* b){
 ++primitive_level;
 if(mode=="primitive_nested" && primitive_level==1)sub_821D51C8(c,b);
 primitive_scale=Fnr3EnginePrimitiveScale(b);
 --primitive_level;
}
extern "C" void __imp__sub_82237568(PPCContext& c,uint8_t* b){
 ++font_level;
 if(mode=="font_nested" && font_level==1)sub_82237568(c,b);
 if(mode!="font_nested" || font_level==1)Fnr3ScaleEngineFontMatrix(c,b);
 --font_level;
}
void Float(uint32_t a,float v){Write32(a,std::bit_cast<uint32_t>(v));}
float FloatAt(uint32_t a){return std::bit_cast<float>(Read32(a));}
int main(int argc,char**argv){try{
 mode=argc>1?argv[1]:"";if(mode.starts_with("720"))resolution="720p";if(mode.starts_with("900"))resolution="900p";
 uint8_t base[1]{};auto c=Pattern(100);expected=c;returned=Pattern(200);returned.r3.u64=1;
 if(mode.starts_with("bloom")){
  Write32(0x6000+24,255|(255<<13));Write32(0x6000+36,0);Write32(0x10000,100);
  Write32(0x10000+11524,(uint32_t(-3)&0x7fff)|((uint32_t(-5)&0x7fff)<<16));Write32(0x10000+11528,1920|(224<<16));
  if(mode=="bloom_fallback")Write32(0x6000+24,1023|(1023<<13));
  Fnr3DrawBloom(c,base,0x6000);Check(draws==1,"draw count");Check(Equal(c,returned),"draw returned context changed");
  if(mode=="bloom_fallback"){Check(rects.empty(),"fallback changed scissor");Check(Read32(0x10000)==124,"fallback cursor");}
  else {Check(rects.size()==2,"scissor scope count");Check(rects[0].x==0&&rects[0].y==0&&rects[0].w==256&&rects[0].h==256,"writer scissor");Check(rects[1].x==-3&&rects[1].y==-5&&rects[1].w==1920&&rects[1].h==224,"signed15 restore");Check(Read32(0x10000)==156,"PM4 cursor rewound");Check(Read32(0x10000+11528)==(1920|(224<<16)),"logical scissor cache changed");}
 } else if(mode.starts_with("primitive")||mode=="720_primitive"||mode=="900_primitive"){
  Write32(0x8280F24C,mode=="primitive_no_target"?0:0x4000);
  Write32(0x4000+108,mode=="primitive_nonortho"?1:2);
  const auto original=c;const auto before=memory;
  if(mode!="primitive_direct")sub_821D51C8(c,base);
  const auto scale=mode=="primitive_direct"?Fnr3EnginePrimitiveScale(base):primitive_scale;
  const float sx=mode=="720_primitive"||mode=="primitive_nonortho"||mode=="primitive_no_target"||mode=="primitive_direct"?1.f:mode=="900_primitive"?1.25f:1.5f;
  Check(184.f*scale[0]==184.f*sx && 600.f*scale[1]==600.f*sx,"primitive authored coordinates");
  Check(Equal(c,original),"primitive context changed");
  for(const auto& [address,value]:before)Check(memory[address]==value,"primitive source or render state changed");
  Check(Fnr3EnginePrimitiveScale(base)==std::array<float,2>{1.f,1.f},"UI primitive scope leaked");
 } else if(mode.starts_with("font")||mode=="720_font"){
  Write32(0x8280F24C,0x4000);Write32(0x4000+108,mode=="font_nonortho"?1:2);memory[0x2000+92]=mode=="font_3d"?3:0;
  for(unsigned i=0;i<16;++i)Float(0x3050+i*4,float(i+1));
  const auto original=c;
  if(mode=="font_apt")Fnr3ScaleEngineFontMatrix(c,base);else sub_82237568(c,base);
  const bool scaled=mode=="font"||mode=="font_nested";
  for(unsigned i=0;i<16;++i)Check(FloatAt(0x3050+i*4)==float(i+1)*(scaled&&i%4<2?1.5f:1.f),"font matrix column/translation/scope");
  Check(Equal(c,original),"font context changed");
  Fnr3ScaleEngineFontMatrix(c,base);for(unsigned i=0;i<16;++i)Check(FloatAt(0x3050+i*4)==float(i+1)*(scaled&&i%4<2?1.5f:1.f),"font TLS scope leaked");
 } else if(mode.starts_with("movie")||mode=="720_movie"){
  c.r3.u64=0x1000;Write32(0x1000+24,0x2000);Write32(0x1000+80,0x3000);Write32(0x2000+148,0x4000);Write32(0x4000+4,0x5000);Write32(0x5000,0x6000);
  Write32(0x4000+76,1);Write32(0x2000+176,mode=="movie_terminal"?5:1);Write32(0x2000+96,mode=="movie_43"?640:1280);Write32(0x2000+100,mode=="movie_43"?480:720);Write32(0x3000+128,1920);Write32(0x3000+132,1080);
  for(unsigned i=0;i<4;++i)Write32(0x6000+std::array<unsigned,4>{20,24,44,48}[i],0x9000+i);
  if(mode=="movie_fail")returned.r3.u64=0;
  sub_82233578(c,base);Check(Equal(c,returned),"movie returned context changed");
  if(mode=="movie_terminal"||mode=="movie_fail"||mode=="720_movie")Check(setters.empty(),"inactive movie mutated");
  else {const float s=mode=="movie_43"?2.25f:1.5f;const float x=mode=="movie_43"?240.f:0.f;Check(setters.size()==4&&setters[0]==x&&setters[1]==0&&setters[2]==s&&setters[3]==s,"movie aspect/center/setters");Check(FloatAt(0x2000+76)==x&&FloatAt(0x4000+64)==s,"movie staging fields");}
 } else if(mode=="physical_null"||mode=="physical_other"){
  c.lr=mode=="physical_other"?0x1234:0x8226DB64;c.r3.u64=448u<<20;bool threw=false;try{sub_8251B4F8(c,base);}catch(const std::runtime_error&){threw=true;}Check(physical_calls==1,"physical original not called");Check(threw==(mode=="physical_null"),"physical fallback guard");
 } else if(mode.ends_with("budget")||mode=="budget_other"){
  const unsigned extra=mode.starts_with("720")?0:mode.starts_with("900")?17:35;Write32(0x827FCE80,400u<<20);Write32(0x2000+4,244u<<20);c.r3.u64=0x2000;c.lr=mode=="budget_other"?1:0x8226D5C4;
  sub_8226DAE0(c,base);sub_8226DEB0(c,base);Check(root_calls==1&&child_calls==1,"allocator original not called");Check(Read32(0x827FCE80)==((400u+std::min(32u,extra))<<20),"root must leave at least80MiB for external physical allocations");Check(Read32(0x2000+4)==((244u+(mode=="budget_other"?0:extra))<<20),"child caller budget");
 } else throw std::runtime_error("unknown contract");
 std::cout<<"PASS "<<mode<<"\n";return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}}
'''

def generate(root: Path, output: Path):
    includes = output / 'include'
    for name,text in {
        'rex/ppc/context.h':CONTEXT,
        'generated/default/fnr3_init.h':INIT,
        'rex/cvar.h':'#pragma once\n#include <string>\nnamespace rex::cvar { std::string GetFlagByName(const char*); }\n',
        'rex/logging.h':'#pragma once\nnamespace rex { [[noreturn]] void FatalError(const char*); }\n#define REXLOG_WARN(...) ((void)0)\n#define REXLOG_INFO(...) ((void)0)\n'
    }.items():
        path=includes/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
    source=output/'canvas.cpp'
    source.write_text(HARNESS.replace('PRODUCTION_CPP',(root/'src/port_resolution.cpp').as_posix()))
    return source,includes
