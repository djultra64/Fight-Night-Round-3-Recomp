# Fight Night Round 3 Recomp

**Version 1.0 · Project work by [djultra64](https://github.com/djultra64)**

An unofficial PC recompilation of Fight Night Round 3 for Xbox 360, built with ReXGlue and the Xenos renderer: Vulkan on Linux and Windows. Version 1.0 brings native 60 FPS gameplay while preserving the original gameplay speed, with configurable resolution and a native settings interface.

You must supply your own supported USA game data. No disc images, XEX executables, generated PowerPC source files, or extracted/game-derived asset files are included in the public distribution. The runtime binary contains compiled translated game code. This project is not affiliated with or endorsed by the game's original publishers or developers.

## Release status

Version 1.0 is a regular release with Linux and Windows Vulkan runtime packages and source build support. Intermittent loading, text and audio issues remain; complete game compatibility and uninterrupted play are not guaranteed.

Read the [known issues](docs/beta/known-issues.md) before installing. Downloads are available through [GitHub Releases](https://github.com/djultra64/Fight-Night-Round-3-Recomp/releases).

## Features

- Native **OPTIONS → GRAPHICS** page with resolution, fullscreen, FXAA and texture filtering.
- A single resolution selector: 720p, 900p, 1080p, 1440p, 1800p and 2160p. The default is 720p.
- Native 60 FPS gameplay with original gameplay speed, stock-rate 30 FPS intros, and 60 FPS replays with elapsed-time updates that preserve slow motion.
- Vulkan presentation and persistent shader/pipeline caching, with parallel compilation and prewarming of cached complete pipelines to reduce repeat compilation stalls.
- **SAVE**, **SAVE AND RESTART**, and **QUIT GAME** integrated into the game's menus.
- Automatic prompts for the last active device, Xbox/PlayStation/Nintendo Switch families, manual family selection, and 14 optional action bindings.
- Local preparation of the native frontend and controller glyphs from verified user-owned assets.

Rendering uses integer scales and downsamples intermediate resolutions: 900p and 1080p use the same 2× rendering tier as 1440p. A lower output resolution within that tier may not reduce GPU cost. Original MSAA is shown as read-only.

Gameplay advances at the native 60 FPS cadence with phase-specific timing; intros retain their stock 30 FPS cadence. Crowd animation uses fractional advancement, and replays use elapsed time to preserve their slow-motion behavior.

A steady 60 FPS requires enough CPU/GPU headroom. Cached pipeline prewarming reduces repeat compilation work, but previously unseen content can still trigger compilation and frame-time spikes.

## Get started

[Download version 1.0](https://github.com/djultra64/Fight-Night-Round-3-Recomp/releases/tag/v1.0): choose the Linux archive or Windows ZIP, extract it into a new folder, then run the supplied launcher.

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

## Help Wanted: frame pacing and higher FPS

Early attempts to remove the frame limiter or simply increase the native frame rate accelerated intros and gameplay and caused audio desynchronization. Keeping simulation at 30 Hz while drawing interpolated frames at 60 Hz made backgrounds and camera movement look smoother, but fighters remained choppy, animation could appear interrupted or slow, and flickering occurred.

Version 1.0 uses a deeper phase-specific cadence approach: native 60 FPS gameplay with original gameplay speed, stock-rate intros, fractional crowd animation advancement, and elapsed-time replay updates that preserve slow motion. This replaces the simple unlock and interpolation approaches above. Smooth pacing still depends on rendering cost, pipeline compilation and the ownership of resources used by each frame.

PRs and forks improving frame pacing, performance or correct higher frame rates are welcome. Preserve natural gameplay speed, phase timing and synchronized audio; a higher presentation counter alone does not establish success. Describe how a change affects gameplay, intros, crowds and replays, and keep further timing experiments optional until their behavior is understood.

## Documentation

- [Installation](docs/beta/installation.md)
- [Building](docs/beta/building.md)
- [Controls and controller prompts](docs/beta/controls.md)
- [Known issues](docs/beta/known-issues.md)
- [Troubleshooting](docs/beta/troubleshooting.md)
- [Version 1.0 release notes](docs/beta/release-notes-1.0.md)
- [Historical beta 0.7 release notes](docs/beta/release-notes-0.7.md)
- [Changelog](CHANGELOG.md), [contributing](CONTRIBUTING.md), [security](SECURITY.md)

## AI Disclosure

I use **OpenAI Codex** to assist with research, reverse-engineering analysis, code implementation, debugging, tests, builds, packaging, and documentation. I direct that work, contribute code reviews and ideas for implementation, evaluate the game's behavior through hands-on testing, and decide which changes and releases to accept. Validation claims remain limited to the recorded builds and scenarios.

The original game and upstream tools remain the work of their respective creators. See [third-party notices](THIRD_PARTY_NOTICES.md).

## Credits and licensing

Original project code is licensed under [BSD-3-Clause](LICENSE). This covers the project’s own work, not the original game or third-party components.

Project work: **djultra64**. ReXGlue, Xenia and all other dependencies retain their authentic authorship and license notices. See [third-party notices](THIRD_PARTY_NOTICES.md). The original game and its assets remain the property of their respective rights holders. No license for original game content is granted by this repository.

This product includes software developed by in <in@fishtank.com>.

This product includes software developed by the Apache Software Foundation (http://www.apache.org/).
