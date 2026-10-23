# Fight Night Round 3 Recomp — beta 0.7

**Beta · Project work by djultra64**

Beta 0.7 targets normal-speed play at the original approximately 30 FPS game clock. Download the Linux archive or Windows runtime ZIP from [GitHub Releases](https://github.com/djultra64/Fight-Night-Round-3-Recomp/releases/tag/v0.7), or follow the [build guide](building.md) for Linux and Windows source builds.

## Included

- Linux and Windows runtime packages with first-run setup and supplied launchers (`launch.sh` / `launch.cmd`).
- Native OPTIONS → GRAPHICS integration and QUIT GAME.
- Unified 720p, 900p, 1080p, 1440p, 1800p and 2160p output selection, fullscreen, FXAA and texture filtering. Original MSAA remains read-only.
- Linux Vulkan Mailbox/VSync presentation and persistent shader caching.
- Saved settings and launcher-managed SAVE AND RESTART.
- Xbox, PlayStation and Nintendo Switch prompt families, automatic last-device tracking, manual family selection and 14 optional action bindings.
- Local frontend/glyph generation from verified user-owned assets.
- Source builds with a pinned, patched ReXGlue SDK and artifact/package audits.

## Compatibility and limitations

The packages require Python 3.12+ and an x86-64-v2 CPU. Linux uses Vulkan and requires a Vulkan 1.3 capable GPU/driver. Windows also uses Vulkan and requires Windows 10 or 11 x64 with a Vulkan 1.3 capable GPU/driver. See [installation requirements](installation.md#what-you-need) for platform details.

Intermittent loading, text and audio issues remain. Complete game compatibility and uninterrupted play are not guaranteed. See [known issues](known-issues.md) for current limitations.

Experimental 60 FPS, interpolation and the alternative native renderer are excluded from the production target. The output resolution selector does not promise performance at every setting; 900p, 1080p and 1440p share the 2× render tier.

No ISO, XEX, generated PowerPC source files or extracted/game-derived asset files are distributed. The runtime binary contains compiled translated game code. Supply the supported USA edition and follow [installation](installation.md). Dependencies retain their own credits and licenses.
