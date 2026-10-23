# Fight Night Round 3 Recomp — 1.0

**Version 1.0 · Project work by djultra64**

Version 1.0 is a regular release for Windows and Linux using Vulkan. It brings native 60 FPS gameplay while preserving original gameplay speed. Download the Linux archive or Windows runtime ZIP from [GitHub Releases](https://github.com/djultra64/Fight-Night-Round-3-Recomp/releases/tag/v1.0), or follow the [build guide](building.md) for source builds.

## Included

- Phase-specific timing: native 60 FPS gameplay, stock-rate 30 FPS intros, fractional crowd animation advancement and 60 FPS replays with elapsed-time updates that preserve slow motion.
- Persistent shader/pipeline caching, parallel compilation and cached complete-pipeline prewarming to reduce repeat compilation stalls. Idle cache flushes now complete promptly, and periodic driver-cache persistence runs on a background worker.
- Notification-driven Linux multi-object waits remove the fixed 1 ms signal latency while retaining bounded recovery for abandoned object locks.
- A fix for a race when retiring texture invalidation watches.
- First-launch import of your supported USA ISO with the supplied launchers (`launch.sh` / `launch.cmd`).
- Native OPTIONS → GRAPHICS integration with 720p, 900p, 1080p, 1440p, 1800p and 2160p output selection, fullscreen, FXAA and texture filtering. Original MSAA remains read-only.
- Saved settings, launcher-managed SAVE AND RESTART and QUIT GAME.
- Xbox, PlayStation and Nintendo Switch prompt families, automatic last-device tracking, manual family selection and 14 optional action bindings. Prompts follow physical layouts, including Nintendo's exchanged A/B and X/Y positions.
- Local frontend/glyph generation from verified user-owned assets and source builds with a pinned, patched ReXGlue SDK.

## Compatibility and limitations

The packages require Python 3.12+ and an x86-64-v2 CPU. Linux and Windows require a Vulkan 1.3 capable GPU/driver; Windows requires Windows 10 or 11 x64. See [installation requirements](installation.md#what-you-need) for platform and Linux binary ABI requirements.

A steady 60 FPS depends on CPU/GPU headroom and the scene being rendered. Higher output resolutions increase GPU cost; 900p, 1080p and 1440p share the 2× render tier. Cached pipeline prewarming reduces repeat compilation work, but previously unseen content can still trigger compilation and frame-time spikes. Neither the resolution selector nor the frame-rate target guarantees uninterrupted pacing at every setting.

Intermittent loading, text and audio issues remain. Complete game compatibility and uninterrupted play are not guaranteed. See [known issues](known-issues.md) and [troubleshooting](troubleshooting.md).

Earlier simple frame-rate unlocks and interpolated presentation experiments are excluded. Contributions improving frame pacing, performance and correct higher frame rates are welcome; see [Help Wanted](../../README.md#help-wanted-frame-pacing-and-higher-fps) and [contributing](../../CONTRIBUTING.md).

No ISO, XEX, generated PowerPC source files or extracted/game-derived asset files are distributed. The runtime binary contains compiled translated game code. Supply the supported USA edition and follow [installation](installation.md). Dependencies retain their own credits and licenses.
