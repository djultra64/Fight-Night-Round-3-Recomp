// Action/physical-position contract. Project work: djultra64.
#pragma once
#include <array>
#include <atomic>
#include <filesystem>
namespace rex::memory { class Memory; }
#include <cstdint>
#include <stdexcept>
#include <string>
#include <string_view>
namespace fnr3::port {
enum class InputFamily { Automatic, Xbox, PlayStation, Switch, Keyboard };
enum class PhysicalButton : unsigned { South, East, West, North, LeftShoulder,
  RightShoulder, LeftStick, RightStick, Start, Back, Up, Down, Left, Right, Count };
// These are guest action channels: the retail control scheme determines their
// combat meaning. Confirm/Cancel are their menu meanings, not combat remaps.
enum class InputAction : unsigned { Confirm, Cancel, AuxiliaryX, AuxiliaryY,
  LeftShoulder, RightShoulder, LeftStick, RightStick, Pause, Back,
  Up, Down, Left, Right, Count };
inline constexpr unsigned kActionCount = unsigned(InputAction::Count);
inline constexpr std::array<uint16_t, kActionCount> kButtonBits = {
  0x1000,0x2000,0x4000,0x8000,0x0100,0x0200,0x0040,0x0080,
  0x0010,0x0020,0x0001,0x0002,0x0004,0x0008};
struct ActionBindings {
  std::array<PhysicalButton, kActionCount> physical{};
  constexpr ActionBindings() { for (unsigned i=0;i<kActionCount;++i) physical[i]=PhysicalButton(i); }
  void Bind(InputAction action, PhysicalButton button) {
    const unsigned a=unsigned(action), b=unsigned(button);
    if (a>=kActionCount || b>=kActionCount) throw std::invalid_argument("Invalid action/button");
    // Swapping keeps a bijection: no lost action or accidental double binding.
    for (unsigned i=0;i<kActionCount;++i) if (physical[i]==button) {
      physical[i]=physical[a]; break;
    }
    physical[a]=button;
  }
  uint16_t Apply(uint16_t raw) const {
    uint16_t mapped=raw & 0x0C00; // Guide and reserved bits stay untouched.
    for(unsigned i=0;i<kActionCount;++i)
      if(raw & kButtonBits[unsigned(physical[i])]) mapped|=kButtonBits[i];
    return mapped;
  }
};
inline constexpr std::string_view FamilyName(InputFamily f) {
  switch(f) { case InputFamily::Automatic:return "Automatic"; case InputFamily::Xbox:return "Xbox";
  case InputFamily::PlayStation:return "PlayStation"; case InputFamily::Switch:return "Nintendo Switch";
  case InputFamily::Keyboard:return "Keyboard / mouse"; } return "Xbox";
}
inline constexpr std::string_view PhysicalLabel(InputFamily f, PhysicalButton p) {
  constexpr std::array<std::string_view,kActionCount> xbox={"A","B","X","Y","LB","RB","LS","RS","Menu","View","Up","Down","Left","Right"};
  constexpr std::array<std::string_view,kActionCount> ps={"Cross","Circle","Square","Triangle","L1","R1","L3","R3","Options","Share","Up","Down","Left","Right"};
  constexpr std::array<std::string_view,kActionCount> sw={"B","A","Y","X","L","R","LS","RS","+","-","Up","Down","Left","Right"};
  if(unsigned(p)>=kActionCount) return "?";
  return (f==InputFamily::PlayStation?ps:f==InputFamily::Switch?sw:xbox)[unsigned(p)];
}
// Host dialogs release gameplay buttons only after the matching physical up.
class GuestButtonGate {
  std::atomic<bool> capture_{false};
  std::atomic<uint16_t> last_{0}, suppressed_{0};
public:
  bool SetCapture(bool capture) {
    const bool previous=capture_.exchange(capture);
    if(previous && !capture) suppressed_.fetch_or(last_.load());
    return previous!=capture;
  }
  void SuppressHeld() {suppressed_.fetch_or(last_.load());}
  bool Captured() const {return capture_.load();}
  uint16_t Filter(uint16_t raw) {
    last_.store(raw);
    const uint16_t suppressed=suppressed_.fetch_and(raw);
    return Captured()?0:uint16_t(raw&~suppressed);
  }
};
struct InputPrompt {
  InputFamily family;
  PhysicalButton physical;
  std::string label; // Actual keybind CVar for keyboard; physical button otherwise.
};
// No event pumping, device opening, assignment or control-driver replacement.
// Install on UI thread after runtime input/window setup; remove before shutdown.
void InitializeInputPrompts();
void ShutdownInputPrompts();
// Call after guest memory exists, before launch; files are generated separately.
// Returns false on unsupported/missing assets and leaves native textures intact.
bool InitializeNativeInputGlyphs(rex::memory::Memory* memory, const std::filesystem::path& root);
struct NativeGlyphStats { uint64_t matches, switches; };
NativeGlyphStats GetNativeGlyphStats();
InputFamily ActiveInputFamily();
// Last detected device family, without the saved manual override.
InputFamily DetectedInputFamily();
InputFamily SelectedInputFamily();
// Call from the host native window key/mouse listener (the SDK window is not an SDL window).
void NotifyKeyboardInput();
void SelectInputFamily(InputFamily family);
InputPrompt PromptFor(InputAction action);
ActionBindings GetActionBindings();
void BindAction(InputAction action, PhysicalButton physical);
void ResetActionBindings();
// Avoid reinterpreting the Save press after changing action bindings.
void SuppressHeldInputButtons();
// Family from SDL's stable public type enumeration, testable without SDL init.
InputFamily FamilyFromSDLType(int type);
struct HostInputSnapshot {
  uint16_t buttons = 0; // Physical-position bits from kButtonBits, before remap.
  int16_t left_x = 0, left_y = 0, right_x = 0, right_y = 0; // SDL: down is positive.
  uint16_t left_trigger = 0, right_trigger = 0;
};
HostInputSnapshot GetHostInputSnapshot();
void SetHostInputCapture(bool capture);
bool HostInputCaptured();
} // namespace fnr3::port
