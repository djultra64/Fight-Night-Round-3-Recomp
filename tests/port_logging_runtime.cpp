// Verify the real SDK no-file sink; use an empty working directory. djultra64.
#include <rex/cvar.h>
#include <rex/logging.h>
#include <filesystem>
#include <iostream>
int main(int argc,char** argv) {
  rex::cvar::Init(argc,argv);
  rex::InitLogging("-", spdlog::level::info);
  rex::ShutdownLogging();
  if(std::filesystem::exists("-") || std::filesystem::exists("logs"))return 1;
  std::cout<<"PASS real SDK no-file logging without an implicit path\n";
}
