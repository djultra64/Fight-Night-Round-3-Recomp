// Windows integration probe. Work: djultra64. Run in a disposable directory.
#include "port_crash_diagnostics.h"
#if defined(_WIN32)
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <filesystem>
#include <string>
LONG CALLBACK Handled(PEXCEPTION_POINTERS info) {
  return info->ExceptionRecord->ExceptionCode == 0xE0424242
      ? EXCEPTION_CONTINUE_EXECUTION : EXCEPTION_CONTINUE_SEARCH;
}
int wmain(int argc, wchar_t** argv) {
  if (argc != 3) return 2;
  std::string error;
  if (!fnr3::port::InstallCrashDiagnostics(std::filesystem::path(argv[1]), &error)) return 3;
  AddVectoredExceptionHandler(1, Handled);
  RaiseException(0xE0424242, 0, 0, nullptr);
  if (std::filesystem::exists(std::filesystem::path(argv[1]) / "crash.dmp")) return 4;
  if (std::wstring(argv[2]) == L"handled") return 0;
  SetErrorMode(SEM_NOGPFAULTERRORBOX);
  RaiseException(0xE0424243, EXCEPTION_NONCONTINUABLE, 0, nullptr);
  return 5;
}
#else
int main() { return 0; }
#endif
