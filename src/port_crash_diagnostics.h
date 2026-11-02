// Optional last-chance Windows crash evidence. Work: djultra64.
#pragma once
#include <filesystem>
#include <string>
namespace fnr3::port {
// Call once during startup. Does not observe handled guest-memory exceptions.
// Best effort: fatal process termination or a broken driver may prevent a dump.
// FNR3_EXPERIMENT_TERMINATE_DUMP=1 additionally opts into a precreated worker
// and a std::terminate handler; its custom-context evidence is not a real SEH.
bool InstallCrashDiagnostics(const std::filesystem::path& directory, std::string* error);
}
