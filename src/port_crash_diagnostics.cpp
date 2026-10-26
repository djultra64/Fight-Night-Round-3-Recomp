// Optional last-chance Windows crash evidence. Work: djultra64.
#include "port_crash_diagnostics.h"
#if defined(_WIN32)
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <dbghelp.h>
#include <array>
#include <cwchar>

namespace {
std::array<wchar_t, 32768> crash_path{};
decltype(&MiniDumpWriteDump) write_dump = nullptr;
LPTOP_LEVEL_EXCEPTION_FILTER previous_filter = nullptr;
volatile LONG dumping = 0;

LONG WINAPI WriteUnhandledDump(EXCEPTION_POINTERS* exception) {
  if (InterlockedCompareExchange(&dumping, 1, 0) == 0 && write_dump) {
    // All DLL resolution and path construction happened before the failure.
    // CREATE_NEW keeps evidence from any earlier crash in this directory.
    HANDLE file = CreateFileW(crash_path.data(), GENERIC_WRITE, 0, nullptr,
                              CREATE_NEW, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file != INVALID_HANDLE_VALUE) {
      MINIDUMP_EXCEPTION_INFORMATION info{GetCurrentThreadId(), exception, FALSE};
      if (!write_dump(GetCurrentProcess(), GetCurrentProcessId(), file,
                      MiniDumpNormal, &info, nullptr, nullptr)) {
        CloseHandle(file);
        DeleteFileW(crash_path.data());
      } else {
        FlushFileBuffers(file);
        CloseHandle(file);
      }
    }
  }
  // Preserve normal Windows/previous-handler crash behavior. No exception is
  // swallowed, and the SDK's vectored handlers have already had their turn.
  return previous_filter ? previous_filter(exception) : EXCEPTION_CONTINUE_SEARCH;
}
}
#endif

namespace fnr3::port {
bool InstallCrashDiagnostics(const std::filesystem::path& directory, std::string* error) {
#if defined(_WIN32)
  if (write_dump) return true;
  std::error_code ec;
  if (!std::filesystem::is_directory(directory, ec)) {
    if (error) *error = "Crash diagnostic directory is unavailable";
    return false;
  }
  const auto path = (directory / "crash.dmp").wstring();
  if (path.size() >= crash_path.size()) {
    if (error) *error = "Crash diagnostic path is too long";
    return false;
  }
  // Load the OS copy before entering any exception handler. Keep it resident
  // for the lifetime of the filter, including the port's intentional _Exit.
  HMODULE library = LoadLibraryExW(L"dbghelp.dll", nullptr, LOAD_LIBRARY_SEARCH_SYSTEM32);
  auto writer = library ? reinterpret_cast<decltype(write_dump)>(
                              GetProcAddress(library, "MiniDumpWriteDump")) : nullptr;
  if (!writer) {
    if (library) FreeLibrary(library);
    if (error) *error = "Windows crash dump support is unavailable";
    return false;
  }
  std::wmemcpy(crash_path.data(), path.c_str(), path.size() + 1);
  write_dump = writer;
  previous_filter = SetUnhandledExceptionFilter(WriteUnhandledDump);
  return true;
#else
  (void)directory;
  if (error) *error = "Crash minidumps are available on Windows";
  return false;
#endif
}
}
