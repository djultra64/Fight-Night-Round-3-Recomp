// CPU-only contract: logical actions and physical positions. Work: djultra64.
#include "port_input.h"
#include <iostream>
#include <cstdlib>
using namespace fnr3::port;
void check(bool condition,const char* message) { if(!condition) {std::cerr<<message<<'\n'; std::exit(1);} }
int main() {
  ActionBindings b;
  for(unsigned raw=0;raw<65536;++raw) check(b.Apply(raw)==raw,"Default mapping changed raw input");
  check(PhysicalLabel(InputFamily::Switch,PhysicalButton::South)=="B","Nintendo south must be B");
  check(PhysicalLabel(InputFamily::Switch,PhysicalButton::East)=="A","Nintendo east must be A");
  check(PhysicalLabel(InputFamily::Switch,PhysicalButton::West)=="Y","Nintendo west must be Y");
  check(PhysicalLabel(InputFamily::Switch,PhysicalButton::North)=="X","Nintendo north must be X");
  check(PhysicalLabel(InputFamily::PlayStation,PhysicalButton::South)=="Cross","PS south");
  b.Bind(InputAction::Confirm,PhysicalButton::East);
  check(b.Apply(0x2000)==0x1000,"Actual confirm action must follow physical remap");
  check(b.Apply(0x1000)==0x2000,"Displaced cancel must stay accessible");
  check(PhysicalLabel(InputFamily::Switch,b.physical[unsigned(InputAction::Confirm)])=="A","Prompt must follow remap");
  for(unsigned raw=0;raw<65536;++raw) check(b.Apply(b.Apply(raw))==raw,"Swap loses simultaneous buttons");
  bool rejected=false; try {b.Bind(InputAction::Count,PhysicalButton::South);}catch(const std::invalid_argument&){rejected=true;}
  check(rejected,"Invalid binding must fail");
  GuestButtonGate gate;
  check(gate.Filter(0x1010)==0x1010,"Gameplay input pass-through");
  check(gate.SetCapture(true),"Capture starts");
  check(gate.Filter(0x1010)==0,"Host captures held Confirm/Menu");
  check(gate.SetCapture(false),"Capture closes");
  check(gate.Filter(0x1010)==0,"Held close input must not leak into native UI");
  check(gate.Filter(0x1000)==0,"Held face remains suppressed after Menu release");
  check(gate.Filter(0)==0,"Release rearms buttons");
  check(gate.Filter(0x1000)==0x1000,"New physical press reaches gameplay");
  gate.SuppressHeld();
  check(!gate.Captured(),"One-shot suppression must not capture input");
  check(gate.Filter(0x3000)==0x2000,"Held Save suppressed while a fresh button still reaches guest");
  check(gate.Filter(0)==0,"Physical release clears one-shot suppression");
  check(gate.Filter(0x1000)==0x1000,"Held Save rearms after release");
  std::cout<<"port input contract passed (Release-safe checks, full 16-bit states)\n";
}
