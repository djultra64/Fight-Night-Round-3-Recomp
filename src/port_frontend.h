// Verified local frontend overlays. Project work: djultra64.
#pragma once
#include <array>
#include <algorithm>
#include <vector>
#include <string>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <stdexcept>
#include <string_view>
namespace rex::filesystem {class VirtualFileSystem;}
namespace fnr3::port {
struct FrontendFile {std::string_view relative;uint64_t source,override_hash;};
inline constexpr std::array<FrontendFile,4> kFrontendFiles={{{
 "gui/fn2k6/screengroups/mainmenu/mainmenu.big",0xc6ad9ee8eabfe05eull,0x2f97ef8ecde6d538ull},{
 "gui/fn2k6/screengroups/options/options.big",0x5b8d5d26e63f2f92ull,0xf4a1a8fad6fb739eull},{
 "gui/fn2k6/screengroups/cac/cac.big",0x5cbb2870da7d89b4ull,0x50b1feb2cbbd4296ull},{
 "locale/ENGLISH.loc",0x89fcf882636eaf89ull,0x7c71267e53f94024ull}}};
inline constexpr std::array<FrontendFile,9> kFrontendSiblings={{{
 "gui/fn2k6/screengroups/mainmenu/t3436t55.tmp",0x611dae6cfcfb0fecull,0x611dae6cfcfb0fecull},{
 "locale/xloc_fe.euk",0x288b3d802aaf2142ull,0x288b3d802aaf2142ull},{
 "locale/xloc_fe.eus",0x6190f11998cd3512ull,0x6190f11998cd3512ull},{
 "locale/xloc_fe.fre",0x5006bb6263c29d9dull,0x5006bb6263c29d9dull},{
 "locale/xloc_fe.ger",0x747d0b4372533b5aull,0x747d0b4372533b5aull},{
 "locale/xloc_gm.euk",0xc49284a094cc963bull,0xc49284a094cc963bull},{
 "locale/xloc_gm.eus",0xc268024593fad2feull,0xc268024593fad2feull},{
 "locale/xloc_gm.fre",0x707c6af8b6ff9180ull,0x707c6af8b6ff9180ull},{
 "locale/xloc_gm.ger",0xf0162179a6bdd8ecull,0xf0162179a6bdd8ecull}}};
// Runtime fingerprints detect changed inputs/outputs; the asset generator
// separately enforces the original SHA-256 pins before producing any file.
inline uint64_t FrontendFingerprint(const std::filesystem::path& path){
 auto n=std::filesystem::file_size(path);
 if(!n||n>64*1024*1024)throw std::runtime_error("Unsupported frontend archive size");
 std::ifstream input(path,std::ios::binary);if(!input)throw std::runtime_error("Missing prepared frontend archive");
 uint64_t result=14695981039346656037ull;std::array<char,65536> bytes;
 while(input){input.read(bytes.data(),bytes.size());for(std::streamsize i=0;i<input.gcount();++i){result^=uint8_t(bytes[i]);result*=1099511628211ull;}}
 if(!input.eof())throw std::runtime_error("Cannot read frontend archive");
 return result;
}
inline void ValidateFrontendFiles(const std::filesystem::path& game_data,const std::filesystem::path& overlay){
 auto validate=[&](const auto& files){for(const auto& file:files){
  if(FrontendFingerprint(game_data/file.relative)!=file.source)throw std::runtime_error("Unsupported original frontend archive: "+std::string(file.relative));
  if(FrontendFingerprint(overlay/"assets"/file.relative)!=file.override_hash)throw std::runtime_error("Prepared frontend archive changed: "+std::string(file.relative));
 }};
 validate(kFrontendFiles);validate(kFrontendSiblings);
 // Parent aliases must expose every original sibling, never hide a source
 // file or expose an unverified extra file from a stale override directory.
 for(const auto& file:kFrontendFiles){
  const auto parent=std::filesystem::path(file.relative).parent_path();
  std::vector<std::string> expected;
  for(const auto& item:kFrontendFiles)if(std::filesystem::path(item.relative).parent_path()==parent)expected.emplace_back(std::filesystem::path(item.relative).filename().string());
  for(const auto& item:kFrontendSiblings)if(std::filesystem::path(item.relative).parent_path()==parent)expected.emplace_back(std::filesystem::path(item.relative).filename().string());
  std::sort(expected.begin(),expected.end());
  for(const auto& directory:{game_data/parent,overlay/"assets"/parent}){
   std::vector<std::string> actual;
   for(const auto& item:std::filesystem::directory_iterator(directory))actual.emplace_back(item.path().filename().string());
   std::sort(actual.begin(),actual.end());
   if(actual!=expected)throw std::runtime_error("Unsupported frontend sibling inventory: "+directory.string());
  }
 }
}
void MountFrontendFiles(rex::filesystem::VirtualFileSystem&,const std::filesystem::path& game_data,const std::filesystem::path& overlay);
} // namespace fnr3::port
