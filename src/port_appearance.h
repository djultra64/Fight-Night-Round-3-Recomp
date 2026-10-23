// Hair bake GPU-to-CPU synchronization. Project work: djultra64.
#pragma once
#include <algorithm>
#include <atomic>
#include <cstdint>
#include <mutex>
#include <unordered_set>
#include <vector>
namespace fnr3::port {
inline bool IsHairCompositeCaller(uint64_t caller) noexcept {
 return caller==0x8220B9DC || caller==0x8220BB94;
}
// Preserve the original Resolve virtual-alias conversion, including the
// E/F alias page correction and sub-page offsets in packed mip tails.
inline uint32_t HairResolvePhysicalAddress(uint32_t address) noexcept {
 return (address&0x1FFFFFFFu)+((((address>>20)&0xFFFu)+0x200u)&0x1000u);
}
class TextureBakeReadbacks {
 struct RequestEntry {uint64_t owner;uint32_t address;};
 std::mutex mutex_;
 uint64_t next_=0;
 std::unordered_set<uint64_t> owners_;
 std::vector<RequestEntry> requests_;
 std::atomic<size_t> pending_{0};
public:
 uint64_t Begin(){std::lock_guard lock(mutex_);auto owner=++next_;owners_.insert(owner);return owner;}
 bool Request(uint64_t owner,uint32_t address){
  if(!address||address>=0x20000000u)return false;
  std::lock_guard lock(mutex_);if(!owners_.contains(owner))return false;
  // Each request represents one resolve; packed mips may reuse an address.
  requests_.push_back({owner,address});
  pending_.store(requests_.size(),std::memory_order_release);return true;
 }
 bool Consume(uint32_t address,uint32_t length){
  if(!length||uint64_t(address)+length>0x20000000u||!pending_.load(std::memory_order_acquire))return false;
  std::lock_guard lock(mutex_);
  auto found=std::find_if(requests_.begin(),requests_.end(),[&](const auto& r){return r.address>=address&&uint64_t(r.address)<uint64_t(address)+length;});
  if(found==requests_.end())return false;
  requests_.erase(found);
  pending_.store(requests_.size(),std::memory_order_release);return true;
 }
 void End(uint64_t owner){
  std::lock_guard lock(mutex_);owners_.erase(owner);
  std::erase_if(requests_,[&](const auto& r){return r.owner==owner;});
  pending_.store(requests_.size(),std::memory_order_release);
 }
};
} // namespace fnr3::port
