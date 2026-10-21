// Non-consuming SDL observer and guest action bridge. Project work: djultra64.
#include "port_input.h"
#include <atomic>
#include <cmath>
#include <algorithm>
#include <cstring>
#include <mutex>
#include <sstream>
#include <SDL3/SDL.h>
#include <rex/cvar.h>
#include <rex/ppc/context.h>
#include <rex/types.h>
#if defined(_WIN32)
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
namespace {
decltype(&SDL_AddEventWatch) runtime_sdl_add_event_watch=nullptr;
decltype(&SDL_RemoveEventWatch) runtime_sdl_remove_event_watch=nullptr;
decltype(&SDL_GetGamepads) runtime_sdl_get_gamepads=nullptr;
decltype(&SDL_GetGamepadTypeForID) runtime_sdl_gamepad_type=nullptr;
decltype(&SDL_free) runtime_sdl_free=nullptr;
void ResolveRuntimeSDLObserver() {
  auto module=GetModuleHandleW(L"rexruntime.dll");
  if(!module) module=GetModuleHandleW(L"rexruntimed.dll");
  if(!module) module=GetModuleHandleW(L"rexruntimerd.dll");
  if(!module)throw std::runtime_error("Cannot find runtime SDL observer module");
  runtime_sdl_add_event_watch=reinterpret_cast<decltype(runtime_sdl_add_event_watch)>(GetProcAddress(module,"Fnr3SDLAddEventWatch"));
  runtime_sdl_remove_event_watch=reinterpret_cast<decltype(runtime_sdl_remove_event_watch)>(GetProcAddress(module,"Fnr3SDLRemoveEventWatch"));
  runtime_sdl_get_gamepads=reinterpret_cast<decltype(runtime_sdl_get_gamepads)>(GetProcAddress(module,"Fnr3SDLGetGamepads"));
  runtime_sdl_gamepad_type=reinterpret_cast<decltype(runtime_sdl_gamepad_type)>(GetProcAddress(module,"Fnr3SDLGetGamepadTypeForID"));
  runtime_sdl_free=reinterpret_cast<decltype(runtime_sdl_free)>(GetProcAddress(module,"Fnr3SDLFree"));
  if(!runtime_sdl_add_event_watch || !runtime_sdl_remove_event_watch || !runtime_sdl_get_gamepads || !runtime_sdl_gamepad_type || !runtime_sdl_free)
    throw std::runtime_error("Runtime lacks the single-instance SDL observer ABI");
}
}
#define SDL_AddEventWatch runtime_sdl_add_event_watch
#define SDL_RemoveEventWatch runtime_sdl_remove_event_watch
#define SDL_GetGamepads runtime_sdl_get_gamepads
#define SDL_GetGamepadTypeForID runtime_sdl_gamepad_type
#define SDL_free runtime_sdl_free
#endif
REXCVAR_DEFINE_STRING(fnr3_input_family,"auto","Port/Input","Controller prompt family")
  .allowed({"auto","xbox","playstation","switch"});
REXCVAR_DEFINE_STRING(fnr3_action_bindings,"0,1,2,3,4,5,6,7,8,9,10,11,12,13",
  "Port/Input","Physical positions for logical action channels");
namespace fnr3::port {
namespace {
void PublishNativeBindings();
std::mutex binding_mutex;
ActionBindings bindings;
std::atomic<InputFamily> active{InputFamily::Xbox}, manual{InputFamily::Automatic};
std::atomic<SDL_JoystickID> last_pad{0};
std::atomic<uint32_t> revision{0};
bool installed=false;
std::array<GuestButtonGate,4> button_gates;
std::mutex host_mutex;
HostInputSnapshot host_snapshot;
SDL_JoystickID snapshot_pad=0;
void TrackHost(const SDL_Event& e) {
  const auto id=e.type==SDL_EVENT_GAMEPAD_AXIS_MOTION?e.gaxis.which:e.gbutton.which;
  std::lock_guard lock(host_mutex);
  const bool button_down=e.type==SDL_EVENT_GAMEPAD_BUTTON_DOWN;
  const bool axis_active=e.type==SDL_EVENT_GAMEPAD_AXIS_MOTION && std::abs(int(e.gaxis.value))>16000;
  if(snapshot_pad!=id) {
    if(!button_down && !axis_active) return;
    host_snapshot={};snapshot_pad=id;
  }
  if(e.type==SDL_EVENT_GAMEPAD_AXIS_MOTION) {
    switch(e.gaxis.axis) {
    case SDL_GAMEPAD_AXIS_LEFTX:host_snapshot.left_x=e.gaxis.value;break;
    case SDL_GAMEPAD_AXIS_LEFTY:host_snapshot.left_y=e.gaxis.value;break;
    case SDL_GAMEPAD_AXIS_RIGHTX:host_snapshot.right_x=e.gaxis.value;break;
    case SDL_GAMEPAD_AXIS_RIGHTY:host_snapshot.right_y=e.gaxis.value;break;
    case SDL_GAMEPAD_AXIS_LEFT_TRIGGER:host_snapshot.left_trigger=uint16_t(std::max(0,int(e.gaxis.value)));break;
    case SDL_GAMEPAD_AXIS_RIGHT_TRIGGER:host_snapshot.right_trigger=uint16_t(std::max(0,int(e.gaxis.value)));break;
    }
  } else {
    constexpr uint16_t masks[]={0x1000,0x2000,0x4000,0x8000,0x20,0x400,0x10,0x40,0x80,0x100,0x200,1,2,4,8};
    if(e.gbutton.button<15) {auto mask=masks[e.gbutton.button];
      if(e.gbutton.down)host_snapshot.buttons|=mask;else host_snapshot.buttons&=~mask;}
  }
}
constexpr const char* kKeys[]={"keybind_a","keybind_b","keybind_x","keybind_y",
  "keybind_left_shoulder","keybind_right_shoulder","keybind_lstick_press",
  "keybind_rstick_press","keybind_start","keybind_back","keybind_dpad_up","keybind_dpad_down","keybind_dpad_left","keybind_dpad_right"};
void MarkPad(SDL_JoystickID id) {
  last_pad.store(id);
  active.store(FamilyFromSDLType(int(SDL_GetGamepadTypeForID(id))));
}
bool SDLCALL Observe(void*,SDL_Event* e) {
  if(!e) return true;
  if(e->type==SDL_EVENT_GAMEPAD_BUTTON_DOWN || e->type==SDL_EVENT_GAMEPAD_BUTTON_UP || e->type==SDL_EVENT_GAMEPAD_AXIS_MOTION) TrackHost(*e);
  if(e->type==SDL_EVENT_WINDOW_FOCUS_LOST) {
    SetHostInputCapture(false); std::lock_guard lock(host_mutex);host_snapshot={};
  }
  if(e->type==SDL_EVENT_GAMEPAD_BUTTON_DOWN) MarkPad(e->gbutton.which);
  else if(e->type==SDL_EVENT_GAMEPAD_AXIS_MOTION) {
    // SDL trigger rest is zero; ignore drift and zero/release events.
    const bool trigger=e->gaxis.axis==SDL_GAMEPAD_AXIS_LEFT_TRIGGER || e->gaxis.axis==SDL_GAMEPAD_AXIS_RIGHT_TRIGGER;
    if(trigger?e->gaxis.value>8000:std::abs(int(e->gaxis.value))>16000) MarkPad(e->gaxis.which);
  } else if(e->type==SDL_EVENT_KEY_DOWN && !e->key.repeat) active.store(InputFamily::Keyboard);
  else if(e->type==SDL_EVENT_MOUSE_BUTTON_DOWN) active.store(InputFamily::Keyboard);
  else if(e->type==SDL_EVENT_GAMEPAD_REMOVED && e->gdevice.which==last_pad.load()) {
    last_pad.store(0); active.store(InputFamily::Xbox);
    std::lock_guard lock(host_mutex);host_snapshot={};snapshot_pad=0;
  }
  return true; // SDL watches observe events; nothing removed from queue.
}
void SaveBindings() {
  std::string text;
  for(auto p:bindings.physical) {if(!text.empty())text+=',';text+=std::to_string(unsigned(p));}
  rex::cvar::SetFlagByName("fnr3_action_bindings",text);
}
}
InputFamily FamilyFromSDLType(int type) {
  switch(type) {
    case SDL_GAMEPAD_TYPE_PS3:case SDL_GAMEPAD_TYPE_PS4:case SDL_GAMEPAD_TYPE_PS5:return InputFamily::PlayStation;
    case SDL_GAMEPAD_TYPE_NINTENDO_SWITCH_PRO:case SDL_GAMEPAD_TYPE_NINTENDO_SWITCH_JOYCON_LEFT:
    case SDL_GAMEPAD_TYPE_NINTENDO_SWITCH_JOYCON_RIGHT:case SDL_GAMEPAD_TYPE_NINTENDO_SWITCH_JOYCON_PAIR:return InputFamily::Switch;
    default:return InputFamily::Xbox;
  }
}
void InitializeInputPrompts() {
  if(installed) return;
#if defined(_WIN32)
  ResolveRuntimeSDLObserver();
#endif
  const auto selected=rex::cvar::GetFlagByName("fnr3_input_family");
  manual.store(selected=="switch"?InputFamily::Switch:selected=="playstation"?InputFamily::PlayStation:selected=="xbox"?InputFamily::Xbox:InputFamily::Automatic);
  // Refuse corrupt/duplicate bindings as a unit, preserving safe defaults.
  std::istringstream stream(rex::cvar::GetFlagByName("fnr3_action_bindings"));
  ActionBindings loaded; unsigned seen=0; bool valid=true;
  for(unsigned i=0;i<kActionCount;++i) {
    unsigned p; char comma;
    if(!(stream>>p)||p>=kActionCount||(seen&(1u<<p))) {valid=false;break;}
    loaded.physical[i]=PhysicalButton(p);seen|=1u<<p;
    if(i+1<kActionCount && (!(stream>>comma)||comma!=',')) {valid=false;break;}
  }
  stream>>std::ws;
  if(valid && stream.eof()) {std::lock_guard lock(binding_mutex);bindings=loaded;}
  if(!SDL_AddEventWatch(Observe,nullptr)) throw std::runtime_error("Cannot install input prompt observer");
  installed=true;
  // Observe the already connected set, without opening devices or synthesizing
  // additions. The repaired driver's own discovery and assignments stay intact.
  int count=0;auto* pads=SDL_GetGamepads(&count);
  if(count>0) MarkPad(pads[0]);
  SDL_free(pads);
}
void ShutdownInputPrompts() {
  SetHostInputCapture(false);
  if(installed) {SDL_RemoveEventWatch(Observe,nullptr);installed=false;}
}
InputFamily DetectedInputFamily(){return active.load();}
InputFamily SelectedInputFamily(){return manual.load();}
void NotifyKeyboardInput(){active.store(InputFamily::Keyboard);}
InputFamily ActiveInputFamily(){auto a=active.load();if(a==InputFamily::Keyboard)return a;auto f=manual.load();return f==InputFamily::Automatic?a:f;}
HostInputSnapshot GetHostInputSnapshot(){std::lock_guard lock(host_mutex);return host_snapshot;}
void SetHostInputCapture(bool capture){bool changed=false;for(auto& gate:button_gates)changed=gate.SetCapture(capture)||changed;if(changed)++revision;}
void SuppressHeldInputButtons(){for(auto& gate:button_gates)gate.SuppressHeld();++revision;}
bool HostInputCaptured(){return button_gates[0].Captured();}
void SelectInputFamily(InputFamily f) {
  if(f==InputFamily::Keyboard) throw std::invalid_argument("Keyboard is automatically detected");
  const char* value=f==InputFamily::Xbox?"xbox":f==InputFamily::PlayStation?"playstation":f==InputFamily::Switch?"switch":"auto";
  if(!rex::cvar::SetFlagByName("fnr3_input_family",value)) throw std::runtime_error("Cannot save input family");
  manual.store(f);
}
ActionBindings GetActionBindings(){std::lock_guard lock(binding_mutex);return bindings;}
void BindAction(InputAction a,PhysicalButton p){std::lock_guard lock(binding_mutex);bindings.Bind(a,p);SaveBindings();PublishNativeBindings();++revision;}
void ResetActionBindings(){std::lock_guard lock(binding_mutex);bindings=ActionBindings{};SaveBindings();PublishNativeBindings();++revision;}
InputPrompt PromptFor(InputAction a) {
  if(unsigned(a)>=kActionCount) throw std::invalid_argument("Invalid input action");
  auto b=GetActionBindings();auto p=b.physical[unsigned(a)];auto f=ActiveInputFamily();
  if(f==InputFamily::Keyboard) {
    const char* key=kKeys[unsigned(p)];
    return {f,p,key?rex::cvar::GetFlagByName(key):"Arrow / stick direction"};
  }
  return {f,p,std::string(PhysicalLabel(f,p))};
}
uint16_t MapGuestButtons(uint16_t raw){return GetActionBindings().Apply(raw);}
uint32_t BindingRevision(){return revision.load();}
} // namespace fnr3::port

// Retail wrapper is the only generated call site of XamInputGetState. Preserve
// its original import call/status, null queries, triggers, axes and user index.
extern "C" void __imp__sub_8251AA38(PPCContext&,uint8_t*);
extern "C" void sub_8251AA38(PPCContext& ctx,uint8_t* base) {
  const uint32_t state=ctx.r4.u32;
  const uint32_t user=ctx.r3.u32;
  __imp__sub_8251AA38(ctx,base);
  if(ctx.r3.u32!=0 || state==0) return;
  auto& raw_buttons=*reinterpret_cast<rex::be<uint16_t>*>(base+state+4);
  const uint16_t filtered=fnr3::port::button_gates[user<4?user:0].Filter(uint16_t(raw_buttons));
  auto& packet=*reinterpret_cast<rex::be<uint32_t>*>(base+state);
  packet=uint32_t(packet)+fnr3::port::BindingRevision();
  if(fnr3::port::HostInputCaptured()) {
    // All twelve gamepad bytes are controls; packet remains valid and updated.
    std::memset(base+state+4,0,12);
    return;
  }
  auto& buttons=*reinterpret_cast<rex::be<uint16_t>*>(base+state+4);
  buttons=fnr3::port::MapGuestButtons(filtered);

}

#define FNR3_GLYPH_BRIDGE_HOST
#include "../tools/port-input/input_glyph_bridge.h"
#include <rex/memory.h>
#include <rex/logging.h>
#include <fstream>
#include <memory>
#include <vector>
namespace fnr3::port {
namespace {
NativeGlyphBridge native_bridge;
std::atomic<bool> native_ready{false};
// Immutable after publication; no GPU can retain a dangling original pointer.
std::vector<std::vector<uint8_t>> native_originals;
std::vector<NativeGlyphRecord> native_records;
constexpr std::array<const char*,16> native_names={"x","t","c","s","l1","r1","l3","r3","str","back","up","dwn","lft","rht","l2","r2"};
std::vector<uint8_t> ReadNativeTexture(const std::filesystem::path& path) {
  std::ifstream file(path,std::ios::binary);
  if(!file)throw std::runtime_error("Missing native glyph asset: "+path.string());
  std::vector<uint8_t> data((std::istreambuf_iterator<char>(file)),{});
  auto be32=[&](size_t p)->uint32_t{if(p+4>data.size())throw std::runtime_error("Truncated glyph archive");return uint32_t(data[p])<<24|uint32_t(data[p+1])<<16|uint32_t(data[p+2])<<8|data[p+3];};
  if(data.size()<16 || std::memcmp(data.data(),"BIGF",4))throw std::runtime_error("Invalid glyph archive");
  size_t pos=16;const auto count=be32(8);
  for(uint32_t i=0;i<count;++i){auto offset=be32(pos),size=be32(pos+4);pos+=8;size_t start=pos;
    while(pos<data.size() && data[pos])++pos;
    if(pos==data.size())throw std::runtime_error("Invalid glyph archive entry");
    std::string name(reinterpret_cast<const char*>(data.data()+start),pos-start);++pos;
    if(name.ends_with(".arena")){
      if(size!=0x5028 || uint64_t(offset)+size>data.size() || std::memcmp(data.data()+offset,"\x89RW4xb2\0",8))throw std::runtime_error("Unsupported native glyph arena");
      return {data.begin()+offset+0x1000,data.begin()+offset+0x5000};
    }
  }
  throw std::runtime_error("Glyph archive has no arena");
}
void PublishNativeBindings() {
  uint64_t packed=native_bridge.controls.load(std::memory_order_relaxed)&0xFF00000000000000ull;
  for(unsigned i=0;i<kActionCount;++i)packed|=uint64_t(unsigned(bindings.physical[i]))<<(i*4);
  native_bridge.controls.store(packed,std::memory_order_release);
}
}
bool InitializeNativeInputGlyphs(rex::memory::Memory* memory,const std::filesystem::path& root) {
  if(native_ready.load())return true;
  if(!memory)return false;
  if(!rex::cvar::GetFlagInfo("fnr3_native_glyph_abi") || rex::cvar::GetFlagByName("fnr3_native_glyph_abi")!="1") {
    REXLOG_ERROR("FNR3 GPU plugin lacks native glyph ABI version 1");return false;
  }
  // Validate every source before allocating/publishing any replacement.
  std::vector<std::vector<uint8_t>> prepared;
  try {
    for(const char* platform:{"XBOX","XENON"})for(const char* family:{"xbox","playstation","switch"})for(const auto* name:native_names)
      prepared.push_back(ReadNativeTexture(root/family/"gui/cafe/artAssets"/platform/"icons"/(std::string(name)+".big")));
  }catch(const std::exception& e){REXLOG_ERROR("FNR3 native glyphs unavailable: {}",e.what());return false;}
  const uint32_t size=uint32_t(prepared.size())*kGlyphTextureBytes;
  uint32_t allocation=memory->SystemHeapAlloc(size,4096,rex::memory::kSystemHeapPhysical);
  if(!allocation){REXLOG_ERROR("FNR3 cannot allocate native glyph textures");return false;}
  const uint32_t physical=memory->GetPhysicalAddress(allocation);
  if(physical==UINT32_MAX || (physical&4095) || uint64_t(physical)+size>0x20000000){memory->SystemHeapFree(allocation);return false;}
  for(unsigned i=0;i<prepared.size();++i)std::memcpy(memory->TranslatePhysical(physical+i*kGlyphTextureBytes),prepared[i].data(),kGlyphTextureBytes);
  native_originals.reserve(30);native_records.reserve(30);
  for(unsigned platform=0;platform<2;++platform)for(unsigned icon=0;icon<native_names.size();++icon){
    if(icon==9)continue; // Synthetic View/Share source is a remap target only.
    native_originals.push_back(std::move(prepared[platform*48+icon]));
    NativeGlyphRecord record{};record.original=native_originals.back().data();record.hash=GlyphHash(record.original);record.action=icon<14?int32_t(icon):-1;
    for(unsigned f=0;f<3;++f)for(unsigned p=0;p<14;++p){
      unsigned target=record.action<0?icon:p;
      record.pages[f][p]=(physical+((platform*48+f*16+target)*kGlyphTextureBytes))>>12;
    }
    native_records.push_back(record);
  }
  {std::lock_guard lock(binding_mutex);PublishNativeBindings();}
  native_bridge.records=native_records.data();native_bridge.count=uint32_t(native_records.size());
  native_ready.store(true,std::memory_order_release);
  REXLOG_INFO("FNR3 prepared {} native glyph identities, {} KiB immutable physical textures",native_records.size(),size/1024);
  return true;
}
NativeGlyphStats GetNativeGlyphStats(){return {native_bridge.matches.load(),native_bridge.switches.load()};}
}
extern "C" FNR3_GLYPH_EXPORT fnr3::port::NativeGlyphBridge* Fnr3GetInputGlyphBridge() {
  using namespace fnr3::port;
  if(!native_ready.load(std::memory_order_acquire))return nullptr;
  auto f=ActiveInputFamily();
  const uint64_t family=f==InputFamily::PlayStation?1:f==InputFamily::Switch?2:0;
  auto controls=native_bridge.controls.load(std::memory_order_relaxed);
  while(!native_bridge.controls.compare_exchange_weak(controls,(controls&0x00FFFFFFFFFFFFFFull)|(family<<56),std::memory_order_release,std::memory_order_relaxed)) {}
  return &native_bridge;
}
