// Texture bake request lifetime and GPU-thread matching. Work: djultra64.
#ifdef NDEBUG
#undef NDEBUG
#endif
#include "port_appearance.h"
#include <cassert>
#include <thread>
#include <iostream>
using namespace fnr3::port;
int main(){
 assert(HairResolvePhysicalAddress(0xCE001000)==0x0E001000);
 assert(HairResolvePhysicalAddress(0xDE001480)==0x1E001480);
 assert(HairResolvePhysicalAddress(0xEE001480)==0x0E002480);
 assert(HairResolvePhysicalAddress(0xFE001480)==0x1E002480);
 TextureBakeReadbacks q;
 auto first=q.Begin();
 assert(!q.Request(first,0));
 assert(!q.Request(first,0x20000000));
 assert(q.Request(first,0x0E001000));
 assert(!q.Consume(0x100000,4096));
 assert(!q.Consume(0x0E001000,0));
 assert(!q.Consume(0x1FFFF000,0xFFFFFFFF));
 assert(q.Consume(0x0E000000,8192));
 assert(!q.Consume(0x0E001000,4096));
 q.End(first);
 auto second=q.Begin(),third=q.Begin();
 assert(q.Request(second,0x2000)&&q.Request(third,0x3000));
 q.End(second);assert(!q.Consume(0x2000,4096));
 assert(q.Consume(0x3000,4096));q.End(third);
 auto canceled=q.Begin();assert(q.Request(canceled,0x4000));q.End(canceled);
 assert(!q.Consume(0x4000,4096));
 auto owner=q.Begin();assert(q.Request(owner,0x5000));assert(q.Request(owner,0x5000));
 unsigned hits=0;std::thread gpu([&]{hits=q.Consume(0x5000,4096);});gpu.join();
 assert(hits==1&&q.Consume(0x5000,4096));
 assert(!q.Consume(0x5000,4096));
 assert(q.Request(owner,0x180000)&&q.Request(owner,0x190000));
 assert(q.Consume(0x180000,65536)&&q.Consume(0x190000,16384));
 assert(!q.Consume(0x180000,65536));q.End(owner);
 assert(!q.Request(owner,0x6000));
 assert(IsHairCompositeCaller(0x8220B9DC)&&IsHairCompositeCaller(0x8220BB94));
 assert(!IsHairCompositeCaller(0x82241360));
 std::cout<<"PASS one-shot physical texture readback, independent owners and scope retirement\n";
}
