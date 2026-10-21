# Fight Night Round 3 Recomp

**Public beta 0.7 · Project work by DJ Ultra 64 ([djultra64](https://github.com/djultra64))**

An unofficial PC recompilation of Fight Night Round 3 for Xbox 360, built with ReXGlue and the Xenos renderer: Vulkan on Linux and Windows. The current goal is the original game timing, approximately 30 FPS, with configurable resolution and a native settings interface.

You must supply your own supported USA game data. No disc images, XEX executables, generated PowerPC source files, or extracted/game-derived asset files are included in the public distribution. The runtime binary contains compiled translated game code. This project is not affiliated with or endorsed by the game's original publishers or developers.

## Beta status

Beta 0.7 includes Linux and Windows runtime packages and source build support. Intermittent loading, text and audio issues remain; complete game compatibility and uninterrupted play are not guaranteed.

Read the [known issues](docs/beta/known-issues.md) before installing. Downloads are available through [GitHub Releases](https://github.com/djultra64/Fight-Night-Round-3-Recomp/releases).

## Features

- Native **OPTIONS → GRAPHICS** page with resolution, fullscreen, FXAA and texture filtering.
- A single resolution selector: 720p, 900p, 1080p, 1440p, 1800p and 2160p. The default is 720p.
- Linux Vulkan Mailbox/VSync presentation and persistent shader caching.
- **SAVE**, **SAVE AND RESTART**, and **QUIT GAME** integrated into the game's menus.
- Automatic prompts for the last active device, Xbox/PlayStation/Nintendo Switch families, manual family selection, and 14 optional action bindings.
- Local preparation of the native frontend and controller glyphs from verified user-owned assets.

Rendering uses integer scales and downsamples intermediate resolutions: 900p and 1080p use the same 2× rendering tier as 1440p. A lower output resolution within that tier may not reduce GPU cost. Original MSAA is shown as read-only. The production target preserves the original game clock; experimental 60 FPS and interpolation work is outside this beta.

## Get started

[Download beta 0.7](https://github.com/djultra64/Fight-Night-Round-3-Recomp/releases/tag/v0.7): choose the Linux archive or Windows ZIP, extract it into a new folder, then run the supplied launcher.

Linux:

```sh
./launch.sh
```

Windows (PowerShell):

```powershell
.\launch.cmd
```

Both packages require Python 3.12+ and an x86-64-v2 CPU. Linux requires a Vulkan 1.3 capable GPU/driver; Windows requires Windows 10 or 11 x64 and a Vulkan 1.3 capable GPU/driver. First-run setup prompts for your own supported USA ISO, verifies it and prepares a private installation before starting the game. Allow at least 5 GiB of free space plus room for caches. Follow [installation and first launch](docs/beta/installation.md) for requirements and exact supported input hashes. To build from source, use the [build guide](docs/beta/building.md).

For an existing supported extraction, pass its location instead:

```sh
./launch.sh --game-data-root "/absolute/path/to/game-data"
```

```powershell
.\launch.cmd --game-data-root "C:\Games\FNR3-data"
```

Use the supplied launcher so that local asset preparation and **SAVE AND RESTART** work correctly. Saves, settings, logs and caches are stored outside the package.

## Help Wanted: 60 FPS

We explored removing the frame limiter and increasing the native frame rate. Those approaches accelerated intros and gameplay and caused audio desynchronization. We also explored keeping simulation at 30 Hz while drawing interpolated frames at 60 Hz. Backgrounds and camera movement could look smoother, but fighters remained choppy, animation could appear interrupted or slow, and flickering occurred. These approaches are not included in the beta.

The research points toward deeper separation of simulation timing from rendering, including interpolation of skinned fighter poses and safe ownership of the GPU resources used by each frame. Repeating scene draws can also advance game state or reduce the actual simulation rate when rendering falls behind. These are engineering leads, not a proven explanation for every artifact or a completed 60 FPS solution.

PRs and forks exploring proper 60 FPS are welcome. The goal is distinct, smoothly animated frames while preserving natural gameplay speed, original timing and synchronized audio. Please keep experiments optional and preserve the original 30 FPS path; a higher presentation counter alone does not establish success.

## Documentation

- [Installation](docs/beta/installation.md)
- [Building](docs/beta/building.md)
- [Controls and controller prompts](docs/beta/controls.md)
- [Known issues](docs/beta/known-issues.md)
- [Troubleshooting](docs/beta/troubleshooting.md)
- [Beta 0.7 release notes](docs/beta/release-notes-0.7.md)
- [Changelog](CHANGELOG.md), [contributing](CONTRIBUTING.md), [security](SECURITY.md)

## AI Disclosure

I use **OpenAI Codex** to assist with research, reverse-engineering analysis, code implementation, debugging, tests, builds, packaging, and documentation. I direct that work, contribute code reviews and ideas for implementation, evaluate the game's behavior through hands-on testing, and decide which changes and releases to accept. Validation claims remain limited to the recorded builds and scenarios.

The original game and upstream tools remain the work of their respective creators. See [third-party notices](THIRD_PARTY_NOTICES.md).

## Credits and licensing

Original project code is licensed under [BSD-3-Clause](LICENSE). This covers the project’s own work, not the original game or third-party components.

Project work: **DJ Ultra 64 — djultra64**. ReXGlue, Xenia and all other dependencies retain their authentic authorship and license notices. See [third-party notices](THIRD_PARTY_NOTICES.md). The original game and its assets remain the property of their respective rights holders. No license for original game content is granted by this repository.

This product includes software developed by in <in@fishtank.com>.

This product includes software developed by the Apache Software Foundation (http://www.apache.org/).
