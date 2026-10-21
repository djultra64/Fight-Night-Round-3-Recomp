// Transactional values for the original APT graphics page. Work: djultra64.
#pragma once
#include "port_settings.h"
#include <algorithm>
namespace fnr3::port {
class NativeGraphicsSession {
 PortSettings pending_;
 bool active_=false;
 static constexpr std::array<const char*,6> resolutions_={"720p","900p","1080p","1440p","1800p","2160p"};
 static constexpr std::array<const char*,3> effects_={"none","fxaa","fxaa_extreme"};
 static constexpr std::array<const char*,6> filters_={"original","1x","2x","4x","8x","16x"};
 static constexpr std::array<const char*,4> families_={"auto","xbox","playstation","switch"};
 template<size_t N> static int Index(const std::array<const char*,N>& values,const std::string& s){
  auto i=std::find(values.begin(),values.end(),s);if(i==values.end())throw std::invalid_argument("Invalid native graphics value");return int(i-values.begin());
 }
 void RequireActive()const{if(!active_)throw std::logic_error("Native graphics page is inactive");}
public:
 bool Active()const{return active_;}
 static int Count(int field){constexpr int counts[]={6,2,3,6,4};if(field<0||field>=5)throw std::invalid_argument("Invalid native graphics field");return counts[field];}
 void Begin(const PortSettings& initial){(void)SerializePortSettings(initial);pending_=initial;active_=true;}
 void Cancel(){active_=false;}
 int Get(int field)const{
  RequireActive();(void)Count(field);
  switch(field){case 0:return Index(resolutions_,pending_.graphics.resolution);case 1:return pending_.graphics.fullscreen?1:0;
   case 2:return Index(effects_,pending_.graphics.post_effect);case 3:return Index(filters_,pending_.graphics.texture_filter);default:return Index(families_,pending_.input_family);}
 }
 void Step(int field,int direction){
  RequireActive();if(direction!=-1&&direction!=1)throw std::invalid_argument("Invalid native graphics direction");
  const auto n=Count(field);const auto index=(Get(field)+direction+n)%n;
  switch(field){case 0:pending_.graphics.resolution=resolutions_[index];break;case 1:pending_.graphics.fullscreen=index!=0;break;
   case 2:pending_.graphics.post_effect=effects_[index];break;case 3:pending_.graphics.texture_filter=filters_[index];break;case 4:pending_.input_family=families_[index];break;}
 }
 int GetBinding(int action)const{RequireActive();if(action<0||action>=int(kActionCount))throw std::invalid_argument("Invalid native action");return int(pending_.bindings.physical[action]);}
 void StepBinding(int action,int direction){RequireActive();if(direction!=-1&&direction!=1)throw std::invalid_argument("Invalid native binding direction");auto next=(GetBinding(action)+direction+int(kActionCount))%int(kActionCount);pending_.bindings.Bind(InputAction(action),PhysicalButton(next));}
 void ResetBindings(){RequireActive();pending_.bindings=ActionBindings{};}
 const PortSettings& Pending()const{RequireActive();return pending_;}
 template<class Persist> void Save(Persist&& persist){RequireActive();(void)SerializePortSettings(pending_);persist(pending_);}
};
} // namespace fnr3::port
