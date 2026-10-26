# Startup, rendering and desktop scaling implementation plan

> **For agentic workers:** Use superpowers:executing-plans to implement and verify each task in this isolated checkout.

**Goal:** Apply the compatible improvements from the approved Xerenge/reNut review to FNR3 without regressing the local Options/profile fixes.
**Architecture:** Keep Xenos/Vulkan, the fixed SDK pin and existing caches. Add opt-in SDK policies for physical window dimensions and complete pipelines at draw time, enabled by FNR3. Keep parallel pipeline preparation and add durable per-launch diagnostics. No foreign game hooks, shaders or unlicensed implementation are copied.
**Tech Stack:** C++23, SDL3, Vulkan, Python 3.12+, pinned ReXGlue patches.
**Spec:** The approved review in the parent workspace, `docs/research/xerenge-renut-review-2026-10-26.md`, and the user's instruction to apply its improvements.

## Global constraints

- Base: 5e3cdd7 (1.0.2 plus validated local Options/profile persistence), preserved unchanged.
- User work attributed exclusively to djultra64; authentic third-party attribution retained.
- Xbox/PlayStation/Switch action mapping and prompts remain unchanged and are regression checked.
- Do not publish or replace the installed game during implementation. Candidate packages carry their actual validation status.
- Preserve user saves and caches; diagnostic runs use copied profiles and separate caches.
- Existing persistent/parallel caches are retained. Burnout/reNut-specific depth, shader, frame generation and present-ID code has no equivalent defect established in this backend and is not imported.

## Review focus

1. Mixed DPI monitors, fullscreen restoration and resized windows preserve physical client size and input coordinates.
2. Async pipeline publication, compilation failure and shutdown cannot produce a false successful draw or an inconsistent pipeline/layout pair.
3. Preloading must not race draw-triggered creation or destroy a pipeline still used by the GPU.
4. Restart, launch failure and simultaneous launch diagnostics preserve the previous attempt and never delete saves or caches.
5. Windows crash diagnostics must not conflict with the runtime's handled guest-memory exceptions; no blanket first-chance exception handler.

### Task 1: Physical window dimensions

Files: SDK patch in `patches/`, `src/port_graphics.h`, `tools/port_build.py`, graphics contracts and a compiled SDK window fixture.

- [x] Reproduce the 720p at 150% mismatch in a fixture executing the SDK sizing path.
- [x] Add an opt-in physical-size window policy, enabled in FNR3; preserve default SDK logical sizing.
- [x] Test 100/125/150/200%, non-primary monitor, density conversion, fullscreen and resize bookkeeping.
- [x] Build the SDK window implementation and rerun graphics settings contracts.

### Task 2: Preserve draws and improve pipeline preparation

Files: Vulkan pipeline/command processor SDK patch, runtime flags, compiled concurrency fixtures.

- [x] Reproduce incomplete draw/publication behavior with actual extracted SDK methods.
- [x] Wait for an in-flight pipeline before FNR3 draws; publish pipeline/layout as one completed state and report failure without using a provisional pipeline.
- [x] Use existing background workers to prepare cached pipelines progressively where safe, with draw-time completion and orderly teardown; keep synchronous preload fallback.
- [x] Test delayed completion, failure, repeated lookup, independent pipelines, preload/draw interaction and teardown. Retain device-specific cache validation/persistence.

### Task 3: Durable startup and graphics diagnostics

Files: `tools/port-build/launch.py`, launcher tests, native app diagnostics and build configuration where needed.

- [x] Add failing tests for distinct logs on restart, exit metadata, explicit diagnostic settings and launch failure.
- [x] Save one attempt directory per process launch with timestamps, exit status and log paths. Default logging remains quiet; diagnostics are opt-in.
- [x] Record effective window/render dimensions and pipeline waits/failures without per-draw log flooding. Add Windows unhandled-crash minidumps if compatible with existing runtime exception handling.
- [x] Verify diagnostic failures cannot prevent an otherwise valid game launch, and no automatic retries conceal a crash.

### Task 4: Integration and acceptance

- [x] Run the complete Python suite and compiled contracts; confirm all new SDK patches apply to the fixed pin and build on supported hosts.
- [x] Produce isolated candidate builds/packages where hosts permit. Test cold/warm startup and visual rendering on available hardware, without overstating absent hardware coverage.
- [ ] Controlled baseline/candidate frame-time comparison remains pending. The available GPU was used for interactive validation by the user; the mixed intro/menu/combat trace is not a matched benchmark, and no FPS gain is claimed.
- [x] Perform independent final code review, fix material findings, and save results and remaining hardware limitations.

## Scope accounting

Physical DPI sizing, complete draw submission, cache preparation and durable diagnostics are implementation targets. Persistent driver caches, parallel compilation, write-watch invalidation and resource ownership already exist and must be preserved. reNut present-wait/overlay fallback applies to an extension this renderer does not use; its depth-bias and AMD stream-converter corrections are game/backend-specific. Adding those unrelated paths would not apply a demonstrated FNR3 improvement.

## Report credit

The reported startup/rendering/scaling issue came from **fransisigoswho**. Once the correction is confirmed, mention and thank **fransisigoswho** in the fix/release notes. Do not claim the full user issue reproduced or resolved from unit tests alone.

## Acceptance evidence

See `docs/beta/stability-validation-2026-10-26.md` for the completed builds, regression checks, Linux user smoke test and remaining Windows/DPI/benchmark coverage. Implementation is complete; the original intermittent report still needs confirmation on the affected system.
