# Stability candidate validation — 2026-10-26

Project work: **djultra64**. Report credit: **fransisigoswho**.

## Implemented scope

The candidate applies the compatible findings from the Xerenge/reNut review to the existing Xenos/Vulkan backend. It preserves base `5e3cdd7` (1.0.2 plus the local Options/profile fixes), SDK pin `f5337cdc947ff6d4c4196737e2c807a48f2a1fc2`, and all 25 previous SDK patches. Four additional patches implement:

- Physical window dimensions, including display selection, density changes, fullscreen restoration, delayed window events and fractional-scale resize rounding.
- Completed pipeline/layout publication before drawing, progressive preparation of cached pipelines, and completion of dependent worker jobs before render-target destruction.
- Synchronized graphics-thread dispatch, including concurrent producers and callbacks that enqueue further work.
- An explicit no-file logging destination when no writable diagnostic location is available.

The launcher records each attempt separately, preserves the exit status and only repeats the existing intentional restart status (42). Diagnostic mode adds startup details and best-effort Windows last-chance minidumps. The crash handler leaves handled guest-memory exceptions alone. Logs and dumps remain local.

Existing persistent driver caches, parallel workers and texture invalidation remain in place. Xbox/PlayStation/Switch action mapping and prompts are unchanged. No game-specific shaders, offsets or renderer code were copied from either external repository. reNut's present-ID timeout recovery has no matching path in this backend.

## Completed verification

| Check | Result |
| --- | --- |
| Complete Python suite | 99 passed |
| Compiled SDK behavior fixtures | 5 passed against the freshly prepared, patched SDK |
| Existing compiled port contracts | 9 passed, including input, settings, timing and scaled texture readback |
| Final Linux SDK, game and ISO extractor build | Passed; candidate packaged with artifact hash validation |
| Final Windows SDK, game and ISO extractor build | Passed; candidate packaged with artifact hash validation |
| Real Linux SDK no-file logging probe | Passed; created neither a file named `-` nor an implicit `logs` directory |
| Windows last-chance exception probe | Handled exception: exit 0, no dump. Unhandled exception: abnormal exit and a 37,483-byte dump |
| Independent code review | Material findings corrected; final review reported no additional findings |

The five SDK fixtures execute extracted production methods against controlled OS/driver boundaries. They cover physical sizing at 100/125/150/200%, mixed-monitor and delayed resize events, fractional rounding, delayed/failed pipeline compilation, immutable publication, dependent-resource lifetime, queue uniqueness, shutdown and 8 concurrent dispatch producers.

Reproduce the Python suite with `python3 -m unittest discover -s tests -p 'test_*.py'`. The four new `tests/*_fixture.py` scripts take the prepared SDK directory and print C++23 fixture source; compile with `-O2 -DNDEBUG -pthread`. The existing `pipeline_storage_pacing_fixture.py` additionally takes its output source path. Build and package with the existing `tools/port_build.py` recipe. The optional native probes are `tests/port_logging_runtime.cpp` and `tests/port_crash_diagnostics_probe.cpp`; run them only in disposable directories, since the crash probe deliberately raises an unhandled exception.

## Hardware observations and limits

The Linux candidate ran on AMD Ryzen Z1 Extreme / RADV PHOENIX under SDL X11. The measured client and Vulkan swapchain were both 1280×720 at desktop scale 1. The first run loaded zero pipeline-cache bytes; an intentional settings restart retained its separate log and loaded 646,812 validated bytes on the next attempt. Captures show the intro, title screen, rendered fighters, ring/environment and pause menu. The user played the Linux candidate and confirmed: “Todo se ve bien.”

That confirmation supports the Linux smoke test. It does not establish a repeated cold-start failure rate, the full Windows mixed-DPI matrix, or reproduction and resolution of the original intermittent issue on fransisigoswho's system. New pipeline states may still cause compilation pauses; retaining their draws favors correctness. No sustained-FPS improvement is claimed. The recorded intro/menu/combat sequence is not a controlled baseline/candidate benchmark. ThreadSanitizer was unavailable in the local toolchain; the concurrency fixtures are not a substitute for a sanitizer run.

Windows runtime/DPI testing and the final Windows no-file logging probe remain pending after remote access stopped responding following successful build/package completion. No conclusion is drawn about RTSS/Afterburner involvement. No release has been published.

Thanks to **fransisigoswho** for reporting the startup, missing-rendering and scaling symptoms that prompted these fixes. The changelog retains this credit and states the remaining validation accurately.
