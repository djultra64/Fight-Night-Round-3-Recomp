# Fight Night Round 3 Recomp

**Public beta 0.7 · Project work by DJ Ultra 64 ([djultra64](https://github.com/djultra64))**

An unofficial PC recompilation of Fight Night Round 3 for Xbox 360, built with ReXGlue and the Xenos/Vulkan renderer. The current goal is the original game timing, approximately 30 FPS, with configurable resolution and a native settings interface.

You must supply your own supported USA game data. No disc images, XEX executables, generated PowerPC source files, or extracted/game-derived asset files are included in the public distribution. The runtime binary contains compiled translated game code. This project is not affiliated with or endorsed by the game's original publishers or developers.

## Beta status

Beta 0.7 includes the Linux runtime package and source build support for Linux and Windows. Intermittent loading, text and audio issues remain; complete game compatibility and uninterrupted play are not guaranteed.

Read the [known issues](docs/beta/known-issues.md) before installing. Downloads are available through [GitHub Releases](https://github.com/djultra64/Fight-Night-Round-3-Recomp/releases).

## Features

- Native **OPTIONS → GRAPHICS** page with resolution, fullscreen, FXAA and texture filtering.
- A single resolution selector: 720p, 900p, 1080p, 1440p, 1800p and 2160p. The default is 720p.
- Mailbox presentation with VSync and a persistent shader cache.
- **SAVE**, **SAVE AND RESTART**, and **QUIT GAME** integrated into the game's menus.
- Automatic prompts for the last active device, Xbox/PlayStation/Nintendo Switch families, manual family selection, and 14 optional action bindings.
- Local preparation of the native frontend and controller glyphs from verified user-owned assets.

Rendering uses integer scales and downsamples intermediate resolutions: 900p and 1080p use the same 2× rendering tier as 1440p. A lower output resolution within that tier may not reduce GPU cost. Original MSAA is shown as read-only. The production target preserves the original game clock; experimental 60 FPS and interpolation work is outside this beta.

## Get started

[Download the Linux beta 0.7](https://github.com/djultra64/Fight-Night-Round-3-Recomp/releases/tag/v0.7), extract the archive into a new folder, then run:

```sh
./launch.sh
```

First-run setup prompts for your own supported USA ISO, verifies it and prepares a private installation before starting the game. Allow at least 5 GiB of free space plus room for caches. Follow [installation and first launch](docs/beta/installation.md) for requirements and exact supported input hashes. To build from source, use the [build guide](docs/beta/building.md).

For an existing supported extraction, pass its location instead:

```sh
./launch.sh --game-data-root "/absolute/path/to/game-data"
```

Use the supplied launcher so that local asset preparation and **SAVE AND RESTART** work correctly. Saves, settings, logs and caches are stored outside the package.

## Documentation

- [Installation](docs/beta/installation.md)
- [Building](docs/beta/building.md)
- [Controls and controller prompts](docs/beta/controls.md)
- [Known issues](docs/beta/known-issues.md)
- [Troubleshooting](docs/beta/troubleshooting.md)
- [Beta 0.7 release notes](docs/beta/release-notes-0.7.md)
- [Changelog](CHANGELOG.md), [contributing](CONTRIBUTING.md), [security](SECURITY.md)

## Credits and licensing

Original project code is licensed under [BSD-3-Clause](LICENSE). This covers the project’s own work, not the original game or third-party components.

Project work: **DJ Ultra 64 — djultra64**. ReXGlue, Xenia and all other dependencies retain their authentic authorship and license notices. See [third-party notices](THIRD_PARTY_NOTICES.md). The original game and its assets remain the property of their respective rights holders. No license for original game content is granted by this repository.

This product includes software developed by in <in@fishtank.com>.
