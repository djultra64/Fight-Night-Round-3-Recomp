"""Execute the SDK's actual SDL window-open method against display fixtures.

Project work: djultra64. SDL is the mocked OS boundary, not the sizing code.
"""
from pathlib import Path
import sys


def method(text, signature):
    start = text.index(signature)
    brace = text.index('{', start)
    depth, end = 1, brace + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]


def generate(sdk):
    source = (sdk / 'src/ui/window_sdl.cpp').read_text()
    return (PREFIX + method(source, 'void WindowSDL::RecordWindowedPixelSize(')
            + method(source, 'void WindowSDL::ApplyWindowedPixelSize(')
            + method(source, 'void WindowSDL::UpdateWindowedPixelSize(')
            + method(source, 'void WindowSDL::HandleWindowEvent(')
            + method(source, 'bool WindowSDL::OpenImpl()') + SUFFIX)


PREFIX = r'''
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <string>
#define REX_PLATFORM_MAC 0
#define REXCVAR_GET(x) cfg_##x
#define REXLOG_ERROR(...) ((void)0)
#define REXLOG_WARN(...) ((void)0)
#define REXLOG_INFO(...) ((void)0)
bool cfg_window_size_in_pixels = true;
int cfg_monitor = 0;
float primary_scale = 1.f, display_scale = 1.f, pixel_density = 1.f, shown_density = 0.f;
bool sync_ok=true; int pending_w=0,pending_h=0;
using SDL_WindowFlags = unsigned;
using SDL_DisplayID = unsigned;
constexpr unsigned SDL_WINDOW_RESIZABLE=1, SDL_WINDOW_HIGH_PIXEL_DENSITY=2,
 SDL_WINDOW_HIDDEN=4, SDL_WINDOW_INPUT_FOCUS=8, SDL_WINDOW_MAXIMIZED=16,
 SDL_WINDOW_FULLSCREEN=32, SDL_WINDOW_MINIMIZED=64;
enum { SDL_EVENT_WINDOW_PIXEL_SIZE_CHANGED, SDL_EVENT_WINDOW_RESIZED,
 SDL_EVENT_WINDOW_DISPLAY_SCALE_CHANGED,SDL_EVENT_WINDOW_DISPLAY_CHANGED,
 SDL_EVENT_WINDOW_FOCUS_GAINED,SDL_EVENT_WINDOW_FOCUS_LOST,SDL_EVENT_WINDOW_EXPOSED,
 SDL_EVENT_WINDOW_MINIMIZED,SDL_EVENT_WINDOW_RESTORED,SDL_EVENT_WINDOW_CLOSE_REQUESTED };
struct SDL_Event {int type;struct {int data1,data2;}window;};
struct UISetupEvent {explicit UISetupEvent(void*){}};
struct MonitorUpdateEvent {MonitorUpdateEvent(void*,bool){}};
#define SDL_WINDOWPOS_CENTERED_DISPLAY(x) int(x)
struct SDL_Window {int width=0,height=0; bool fullscreen=false;};
SDL_Window host;
SDL_Window* SDL_CreateWindow(const char*,int w,int h,unsigned) {
 host={w,h,false};pending_w=pending_h=0;display_scale=primary_scale; return &host;
}
const char* SDL_GetError(){return "fixture";}
unsigned SDL_GetWindowID(SDL_Window*){return 1;}
SDL_DisplayID* SDL_GetDisplays(int* n){static SDL_DisplayID d[2]={1,2};*n=2;return d;}
void SDL_free(void*){}
void SDL_SetWindowPosition(SDL_Window*,int display,int){if(display==2)display_scale=2.f;}
void SDL_SetWindowFullscreen(SDL_Window* w,bool b){w->fullscreen=b;}
bool SDL_SetWindowSize(SDL_Window*,int x,int y){pending_w=x;pending_h=y;return true;}
bool SDL_SyncWindow(SDL_Window* w){
 if(!sync_ok)return false;
 if(pending_w){w->width=pending_w;w->height=pending_h;pending_w=pending_h=0;}
 return true;
}
float SDL_GetWindowPixelDensity(SDL_Window* w){return float(std::lround(w->width*pixel_density))/w->width;}
void SDL_GetWindowSize(SDL_Window* w,int* x,int* y){if(x)*x=w->width;if(y)*y=w->height;}
float SDL_GetWindowDisplayScale(SDL_Window*){return display_scale;}
void SDL_ShowWindow(SDL_Window*){if(shown_density>0)pixel_density=shown_density;}
void SDL_GetWindowSizeInPixels(SDL_Window* w,int* x,int* y){
 *x=int(std::lround(w->width*pixel_density));*y=int(std::lround(w->height*pixel_density));
}
unsigned SDL_GetWindowFlags(SDL_Window* w){return w->fullscreen?SDL_WINDOW_FULLSCREEN:0;}
struct WindowDestructionReceiver {explicit WindowDestructionReceiver(void*){} bool IsWindowDestroyed(){return false;}};
struct Context {void RegisterWindow(unsigned,void*){}};
struct WindowSDL {
 SDL_Window* sdl_window_=nullptr;unsigned sdl_window_id_=0;
 unsigned desired_w=1280,desired_h=720,actual_w=0,actual_h=0;bool fullscreen=false;
 unsigned windowed_pixel_width_=0,windowed_pixel_height_=0;
 int windowed_coordinate_width_=0;float windowed_pixel_density_=0;bool windowed_pixel_size_pending_=false;
 void RecordWindowedPixelSize(uint32_t,uint32_t);
 void ApplyWindowedPixelSize();void UpdateWindowedPixelSize();void HandleWindowEvent(SDL_Event&);
 float GetPixelDensity()const{return SDL_GetWindowPixelDensity(sdl_window_);}
 void OnDpiChanged(UISetupEvent&,WindowDestructionReceiver&){}void OnMonitorUpdate(MonitorUpdateEvent&){}
 void OnPaint(bool){}void OnMinimized(WindowDestructionReceiver&){}void OnRestored(WindowDestructionReceiver&){}
 bool SendCloseRequestToListeners(WindowDestructionReceiver&){return false;}void PerformClose(){}
 bool OpenImpl();
 unsigned GetDesiredLogicalWidth()const{return desired_w;}
 unsigned GetDesiredLogicalHeight()const{return desired_h;}
 unsigned SizeToPhysical(unsigned x)const{return unsigned(std::lround(x*(sdl_window_?display_scale:primary_scale)));}
 unsigned SizeToLogical(unsigned x)const{return unsigned(std::lround(x/display_scale));}
 std::string GetTitle()const{return "test";}
 Context& sdl_app_context(){static Context c;return c;}
 bool IsFullscreen()const{return fullscreen;}
 void ApplyTextInputActiveNow(){} void ApplyCursorVisibilityNow(){}
 void OnDesiredLogicalSizeUpdate(unsigned w,unsigned h){desired_w=w;desired_h=h;}
 void OnActualSizeUpdate(unsigned w,unsigned h,WindowDestructionReceiver&){actual_w=w;actual_h=h;}
 void OnFocusUpdate(bool,WindowDestructionReceiver&){}
};
void require(bool ok,const char* why){if(!ok){std::cerr<<why<<'\n';std::exit(1);}}
'''

SUFFIX = r'''
int main(){
 for(float scale : {1.f,1.25f,1.5f,2.f}) {
   primary_scale=scale; pixel_density=1; cfg_monitor=0;
   WindowSDL w; require(w.OpenImpl(),"window did not open");
   require(w.actual_w==1280 && w.actual_h==720,"720p was multiplied by desktop DPI");
   require(w.SizeToPhysical(w.desired_w)==1280,"restoring window would multiply DPI again");
   w.sdl_window_=nullptr;
   require(w.OpenImpl() && w.actual_w==1280,"reopening reinterpreted logical size as pixels");
 }
 // Selected display differs from the primary; size is still physical pixels.
 primary_scale=1.25f; cfg_monitor=2; WindowSDL other;
 require(other.OpenImpl() && other.actual_w==1280,"secondary monitor changed client pixels");
 require(other.SizeToPhysical(other.desired_w)==1280,"secondary monitor restore bookkeeping");
 // A backend whose window coordinates are points must divide by pixel density.
 cfg_monitor=0; primary_scale=2; pixel_density=2; WindowSDL dense;
 require(dense.OpenImpl() && dense.actual_w==1280 && dense.actual_h==720,"backing density applied twice");
 dense.sdl_window_=nullptr;
 require(dense.OpenImpl() && dense.actual_w==1280,"reopening multiplied backing density");
 dense.RecordWindowedPixelSize(1600,900); dense.sdl_window_=nullptr;
 require(dense.OpenImpl() && dense.actual_w==1600 && dense.actual_h==900,"resize lost on reopen");
 pixel_density=1; WindowSDL full;full.fullscreen=true;
 require(full.OpenImpl() && host.fullscreen,"fullscreen behavior lost");
 require(host.width==1280 && host.height==720,"fullscreen restore size is wrong");
 // Hidden Wayland density reflects another monitor; Show resolves the output.
 primary_scale=1;pixel_density=2;shown_density=1;WindowSDL mixed;
 require(mixed.OpenImpl() && mixed.actual_w==1280 && mixed.actual_h==720,"hidden provisional density shrank the window");
 shown_density=0;
 for(bool has_resize : {true,false}) {
   pixel_density=2;
   if(has_resize){SDL_Event e{SDL_EVENT_WINDOW_RESIZED,{1280,720}};mixed.HandleWindowEvent(e);}
   SDL_Event pixels{SDL_EVENT_WINDOW_PIXEL_SIZE_CHANGED,{2560,1440}};mixed.HandleWindowEvent(pixels);
   SDL_Event scale{SDL_EVENT_WINDOW_DISPLAY_SCALE_CHANGED,{0,0}};mixed.HandleWindowEvent(scale);
   require(mixed.actual_w==1280 && mixed.actual_h==720,"density transition changed client pixels");
   pixel_density=1;mixed.HandleWindowEvent(scale);
 }
 // Fullscreen monitor transition must preserve the normal-state target.
 host.fullscreen=true;pixel_density=2;
 SDL_Event scale{SDL_EVENT_WINDOW_DISPLAY_SCALE_CHANGED,{0,0}};mixed.HandleWindowEvent(scale);
 require(mixed.windowed_pixel_density_==1,"fullscreen overwrote windowed density");
 host.fullscreen=false;SDL_Event restore{SDL_EVENT_WINDOW_RESIZED,{1280,720}};mixed.HandleWindowEvent(restore);
 require(host.width==640 && mixed.windowed_pixel_width_==1280,"restored window lost physical size");
 // Failure to sync must retain the target, not record the previous client size.
 sync_ok=false;mixed.windowed_pixel_width_=1600;mixed.windowed_pixel_height_=900;mixed.ApplyWindowedPixelSize();
 mixed.UpdateWindowedPixelSize();
 require(mixed.windowed_pixel_width_==1600,"failed sync replaced target with stale dimensions");
 sync_ok=true;pending_w=pending_h=0;
 pixel_density=1;
 // Fractional rounding changes SDL's measured ratio during manual resizing.
 for(float fraction : {1.25f,1.5f}) {
   primary_scale=fraction;pixel_density=fraction;WindowSDL fractional;
   require(fractional.OpenImpl(),"fractional window failed");
   host.width=1025;host.height=721;
   SDL_Event manual{SDL_EVENT_WINDOW_RESIZED,{1025,721}};fractional.HandleWindowEvent(manual);
   require(host.width==1025 && host.height==721,"manual fractional resize was mistaken for a monitor change");
   require(fractional.windowed_pixel_width_==unsigned(std::lround(1025*fraction)),"manual physical target not recorded");
 }
 pixel_density=1;
 // Other SDK applications retain the default logical-size contract.
 cfg_window_size_in_pixels=false; primary_scale=1.5f;WindowSDL legacy;
 require(legacy.OpenImpl() && legacy.actual_w==1920 && legacy.actual_h==1080,"legacy logical sizing changed");
 std::cout<<"PASS physical window sizing, DPI matrix, display selection, density and fullscreen\n";
}
'''

if __name__ == '__main__':
    print(generate(Path(sys.argv[1])))
