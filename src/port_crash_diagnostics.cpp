// Optional last-chance Windows crash evidence. Work: djultra64.
#include "port_crash_diagnostics.h"
#if defined(_WIN32)
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <dbghelp.h>
#include <array>
#include <cstdlib>
#include <cwchar>
#include <exception>

namespace {
std::array<wchar_t, 32768> crash_path{};
decltype(&MiniDumpWriteDump) write_dump = nullptr;
LPTOP_LEVEL_EXCEPTION_FILTER previous_filter = nullptr;
volatile LONG crash_once = 0;
volatile LONG dbghelp_writer_active = 0;

// Experimental terminate evidence is separate from a real unhandled exception.
// All storage and the worker exist before readiness is published. A second
// fatal path may still terminate the process before any evidence completes.
constexpr DWORD kTerminateDiagnosticCode = 0xE0424654;
constexpr DWORD kTerminateWaitMs = 2000;
std::array<wchar_t, 32768> terminate_path{}, terminate_status_path{};
std::array<char, 512> terminate_what{};
std::array<char, 4096> terminate_status{};
CONTEXT terminate_context{};
EXCEPTION_RECORD terminate_record{};
EXCEPTION_POINTERS terminate_exception{&terminate_record, &terminate_context};
DWORD terminate_thread = 0;
const char* terminate_kind = "unavailable";
bool terminate_what_truncated = false;
HANDLE terminate_request = nullptr, terminate_done = nullptr;
// This CRT maintains terminate handlers per thread. These trivial TLS values
// also work for registration by an SDK thread before host initialization.
thread_local std::terminate_handler previous_terminate = nullptr;
thread_local bool terminate_registered = false;
volatile LONG terminate_ready = 0;
volatile LONG terminating = 0;
// Published by SetEvent(terminate_done); read only after that wait succeeds.
bool terminate_written = false;
DWORD terminate_error = ERROR_SUCCESS;

DWORD WINAPI TerminateDumpWorker(void*) {
  if (WaitForSingleObject(terminate_request, INFINITE) != WAIT_OBJECT_0) return 0;
  // DbgHelp is not thread safe. This gate tracks only an active writer, so a
  // completed unhandled dump can be followed by the CRT's terminate handler.
  // If another writer still owns it, do not wait on its thread or locks.
  if (InterlockedCompareExchange(&dbghelp_writer_active, 1, 0) != 0) {
    terminate_error = ERROR_BUSY;
  } else {
    HANDLE file = CreateFileW(terminate_path.data(), GENERIC_WRITE, 0, nullptr,
                              CREATE_NEW, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file == INVALID_HANDLE_VALUE) {
      terminate_error = GetLastError();
    } else {
      MINIDUMP_EXCEPTION_INFORMATION info{terminate_thread, &terminate_exception, FALSE};
      const BOOL written = write_dump(GetCurrentProcess(), GetCurrentProcessId(), file,
                                     MiniDumpNormal, &info, nullptr, nullptr);
      if (!written) {
        terminate_error = GetLastError();
      } else if (!FlushFileBuffers(file)) {
        terminate_error = GetLastError();
      } else {
        terminate_written = true;
      }
      CloseHandle(file);
      // Retain incomplete evidence, but never label it completed in status.
    }
    InterlockedExchange(&dbghelp_writer_active, 0);
  }
  SetEvent(terminate_done);
  return 0;
}

void WriteTerminateStatus(const char* state, DWORD error) noexcept {
  // Fixed maximum: 511 what bytes expand to at most 3066 JSON bytes. No logger,
  // allocator or C stdio on the fatal path. This I/O itself remains best effort.
  size_t used = 0;
  auto append = [&](const char* text) {
    while (*text) terminate_status[used++] = *text++;
  };
  auto number = [&](DWORD value) {
    char reversed[10];
    size_t count = 0;
    do { reversed[count++] = char('0' + value % 10); value /= 10; } while (value);
    while (count) terminate_status[used++] = reversed[--count];
  };
  append("{\"schema\":1,\"reason\":\"std::terminate\","
         "\"context\":\"diagnostic-pre-termination\",\"status\":\"");
  append(state);
  append("\",\"thread_id\":"); number(terminate_thread);
  append(",\"error\":"); number(error);
  append(",\"exception_kind\":\""); append(terminate_kind);
  append("\",\"what\":\"");
  constexpr char hex[] = "0123456789abcdef";
  for (unsigned char byte : terminate_what) {
    if (!byte) break;
    if (byte == '"' || byte == '\\') {
      terminate_status[used++] = '\\';
      terminate_status[used++] = char(byte);
    } else if (byte < 0x20 || byte >= 0x7F) {
      append("\\u00");
      terminate_status[used++] = hex[byte >> 4];
      terminate_status[used++] = hex[byte & 15];
    } else {
      terminate_status[used++] = char(byte);
    }
  }
  append("\",\"what_truncated\":");
  append(terminate_what_truncated ? "true}\n" : "false}\n");
  HANDLE file = CreateFileW(terminate_status_path.data(), GENERIC_WRITE, 0, nullptr,
                            CREATE_NEW, FILE_ATTRIBUTE_NORMAL, nullptr);
  if (file != INVALID_HANDLE_VALUE) {
    DWORD written = 0;
    WriteFile(file, terminate_status.data(), static_cast<DWORD>(used), &written, nullptr);
    FlushFileBuffers(file);
    CloseHandle(file);
  }
}

[[noreturn]] void WriteTerminateDump();
[[noreturn]] void ChainTerminate() {
  if (previous_terminate && previous_terminate != WriteTerminateDump) previous_terminate();
  // Required only if the previous handler is null or violates its contract by
  // returning. Keep CRT abort behavior; do not manufacture an exit code.
  std::abort();
}

[[noreturn]] void WriteTerminateDump() {
  // An early SDK thread may register before paths, events or DbgHelp exist.
  // In that case preserve its prior handler without touching those resources.
  if (InterlockedCompareExchange(&terminate_ready, 0, 0) == 0) ChainTerminate();
  if (InterlockedCompareExchange(&terminating, 1, 0) != 0) ChainTerminate();
  terminate_thread = GetCurrentThreadId();
  RtlCaptureContext(&terminate_context);
  terminate_record.ExceptionCode = kTerminateDiagnosticCode;
  terminate_record.ExceptionFlags = EXCEPTION_NONCONTINUABLE;
#if defined(_M_X64) || defined(__x86_64__)
  terminate_record.ExceptionAddress = reinterpret_cast<void*>(terminate_context.Rip);
#elif defined(_M_ARM64) || defined(__aarch64__)
  terminate_record.ExceptionAddress = reinterpret_cast<void*>(terminate_context.Pc);
#else
  terminate_record.ExceptionAddress = reinterpret_cast<void*>(terminate_context.Eip);
#endif
  // No signal handler is involved. Exception inspection is still best effort
  // if the heap or the exception object is corrupt; capture context first.
  if (auto exception = std::current_exception()) {
    try {
      std::rethrow_exception(exception);
    } catch (const std::exception& caught) {
      terminate_kind = "std::exception";
      if (const char* message = caught.what()) {
        size_t count = 0;
        while (count + 1 < terminate_what.size() && message[count]) {
          terminate_what[count] = message[count];
          ++count;
        }
        terminate_what_truncated = message[count] != '\0';
      }
    } catch (...) {
      terminate_kind = "other";
    }
  }
  if (!SetEvent(terminate_request)) {
    WriteTerminateStatus("failed", GetLastError());
  } else {
    const DWORD wait = WaitForSingleObject(terminate_done, kTerminateWaitMs);
    if (wait == WAIT_OBJECT_0) {
      WriteTerminateStatus(terminate_written ? "completed" : "failed", terminate_error);
    } else {
      WriteTerminateStatus(wait == WAIT_TIMEOUT ? "timeout" : "failed",
                           wait == WAIT_TIMEOUT ? ERROR_TIMEOUT : GetLastError());
    }
  }
  // The worker may still own its buffers/handles after timeout. Leave them alive
  // until the previous handler ends the process. Do not join/close/free them.
  ChainTerminate();
}

bool PrepareTerminateDiagnostic(const std::filesystem::path& directory, std::string* error) {
  const auto dump = (directory / "terminate.dmp").wstring();
  const auto status = (directory / "terminate-status.json").wstring();
  if (dump.size() >= terminate_path.size() || status.size() >= terminate_status_path.size()) {
    if (error) *error = "Terminate diagnostic path is too long";
    return false;
  }
  std::wmemcpy(terminate_path.data(), dump.c_str(), dump.size() + 1);
  std::wmemcpy(terminate_status_path.data(), status.c_str(), status.size() + 1);
  terminate_request = CreateEventW(nullptr, FALSE, FALSE, nullptr);
  terminate_done = CreateEventW(nullptr, TRUE, FALSE, nullptr);
  HANDLE worker = terminate_request && terminate_done
      ? CreateThread(nullptr, 0, TerminateDumpWorker, nullptr, 0, nullptr) : nullptr;
  if (!worker) {
    if (terminate_request) CloseHandle(terminate_request);
    if (terminate_done) CloseHandle(terminate_done);
    terminate_request = terminate_done = nullptr;
    if (error) *error = "Terminate diagnostic worker is unavailable";
    return false;
  }
  CloseHandle(worker); // Thread and events remain owned by the process lifetime.
  return true;
}

LONG WINAPI WriteUnhandledDump(EXCEPTION_POINTERS* exception) {
  if (InterlockedCompareExchange(&crash_once, 1, 0) == 0 && write_dump
      && InterlockedCompareExchange(&dbghelp_writer_active, 1, 0) == 0) {
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
    // Keep crash_once claimed, but release DbgHelp before the previous filter:
    // a CRT C++ exception filter may now call std::terminate on this thread.
    InterlockedExchange(&dbghelp_writer_active, 0);
  }
  // Preserve normal Windows/previous-handler crash behavior. No exception is
  // swallowed, and the SDK's vectored handlers have already had their turn.
  return previous_filter ? previous_filter(exception) : EXCEPTION_CONTINUE_SEARCH;
}
}

// Private opt-in SDK bridge. No DLL load, worker creation, paths or logging at
// thread entry. Registration is valid before InstallCrashDiagnostics; the
// handler will only use diagnostic resources after terminate_ready is published.
extern "C" __declspec(dllexport)
void Fnr3InstallTerminateDiagnosticsForCurrentThread() noexcept {
  wchar_t opt_in[2]{};
  if (GetEnvironmentVariableW(L"FNR3_EXPERIMENT_TERMINATE_DUMP", opt_in, 2) != 1
      || opt_in[0] != L'1' || terminate_registered) return;
  previous_terminate = std::set_terminate(WriteTerminateDump);
  terminate_registered = true;
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
  wchar_t opt_in[2]{};
  const bool enable_terminate =
      GetEnvironmentVariableW(L"FNR3_EXPERIMENT_TERMINATE_DUMP", opt_in, 2) == 1
      && opt_in[0] == L'1';
  if (enable_terminate && !PrepareTerminateDiagnostic(directory, error)) {
    FreeLibrary(library);
    return false;
  }
  std::wmemcpy(crash_path.data(), path.c_str(), path.size() + 1);
  write_dump = writer;
  previous_filter = SetUnhandledExceptionFilter(WriteUnhandledDump);
  if (enable_terminate) {
    InterlockedExchange(&terminate_ready, 1);
    Fnr3InstallTerminateDiagnosticsForCurrentThread();
  }
  return true;
#else
  (void)directory;
  if (error) *error = "Crash minidumps are available on Windows";
  return false;
#endif
}
}
