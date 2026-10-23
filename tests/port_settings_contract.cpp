// Port-only atomic persistence; Release checks remain enabled. Work: djultra64.
#include "port_settings.h"
#include <cstdlib>
#include <iostream>
using namespace fnr3::port;
void check(bool c,const char* m){if(!c){std::cerr<<m<<'\n';std::exit(1);}}
std::string read(const std::filesystem::path& p){std::ifstream f(p);return {(std::istreambuf_iterator<char>(f)),{}};}
int main(){
 auto root=std::filesystem::temp_directory_path()/("fnr3-settings-contract-"+std::to_string(std::chrono::steady_clock::now().time_since_epoch().count()));
 auto file=root/"port-settings.toml";PortSettings s;
 SavePortSettingsFile(file,s);auto first=read(file);
 check(first.find("fnr3_resolution = \"720p\"")!=std::string::npos,"Default resolution persisted");
 check(first.find("resolution_scale")==std::string::npos&&first.find("input_backend")==std::string::npos,"No backend registry leaked");
 check(first.find("fnr3_frame_rate = \"60\"")!=std::string::npos,"Default 60 FPS persisted");
 s.graphics={"2160p","fxaa_extreme","16x",true,30};s.input_family="switch";s.bindings.Bind(InputAction::Confirm,PhysicalButton::East);
 SavePortSettingsFile(file,s);auto second=read(file);
 check(second!=first&&second.find("fnr3_fullscreen = true")!=std::string::npos,"Atomic replace existing file");
 check(second.find("fnr3_action_bindings = \"1,0,2,3")!=std::string::npos,"Physical permutation persisted");
 check(second.find("fnr3_frame_rate = \"30\"")!=std::string::npos,"30 FPS selection persisted");
 unsigned rejected=0;
 s.graphics.resolution="720p\"\nvsync = false";try{SavePortSettingsFile(file,s);}catch(const std::invalid_argument&){++rejected;}
 check(read(file)==second,"Invalid value cannot damage saved settings");
 s.graphics.resolution="720p";s.input_family="xbox\n";try{(void)SerializePortSettings(s);}catch(const std::invalid_argument&){++rejected;}
 s.input_family="auto";s.bindings.physical[1]=s.bindings.physical[0];try{(void)SerializePortSettings(s);}catch(const std::invalid_argument&){++rejected;}
 check(rejected==3,"All unsafe enum/permutation values rejected");
 unsigned files=0;for(const auto& entry:std::filesystem::directory_iterator(root)){(void)entry;++files;}check(files==1,"No temporary files left behind");
 std::filesystem::remove_all(root);std::cout<<"port settings atomic contract passed\n";
}
