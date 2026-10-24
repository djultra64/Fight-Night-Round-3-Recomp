// GPU descriptor bounds and relative addressing beyond 4 GiB. Work: djultra64.
#ifdef NDEBUG
#undef NDEBUG
#endif
#include "../tools/xenos-optimized/readback_buffer_range.h"
#include <cassert>
#include <iostream>
using namespace fnr3::port;
int main(){
 constexpr uint64_t size=0x20000000ull*9,limit=0xFFFFFFFFull;
 auto a=ReadbackSourceBinding(0x185C9000ull*9,0x400000ull*9,4,size,limit);
 assert(a&&a->offset==0x185C9000ull*9&&a->length==0x400000ull*9&&a->shader_offset==0);
 auto b=ReadbackSourceBinding(0x1F000000ull*9+64,0x10000ull*9,256,size,limit);
 assert(b&&b->offset>0xFFFFFFFFull&&b->offset%256==0&&b->shader_offset==64);
 assert(b->offset+b->shader_offset==0x1F000000ull*9+64&&b->length==0x10000ull*9+64);
 assert(!ReadbackSourceBinding(0,0,4,size,limit));
 assert(!ReadbackSourceBinding(0,4096,0,size,limit));
 assert(!ReadbackSourceBinding(0,4096,3,size,limit));
 assert(!ReadbackSourceBinding(size-4,8,4,size,limit));
 assert(!ReadbackSourceBinding(UINT64_MAX-3,8,4,size,limit));
 assert(!ReadbackSourceBinding(64,limit,256,UINT64_MAX,limit));
 auto edge=ReadbackSourceBinding(size-1024,1024,4,size,limit);assert(edge&&edge->offset+edge->length==size);
 std::cout<<"PASS bounded scaled readback, aligned sub-page offsets and addresses beyond 4 GiB\n";
}
