# Installation and first launch

Download the Linux archive or Windows ZIP from [GitHub Releases](https://github.com/djultra64/Fight-Night-Round-3-Recomp/releases/tag/v1.0.2). See the [build guide](building.md) for Linux and Windows source builds.

## What you need

- Your own supported **USA Xbox 360** edition of Fight Night Round 3.
- A recent Linux x86-64 system with **glibc 2.38+** and libstdc++ providing **GLIBCXX_3.4.32** or newer (GCC 13.2). These are the packaged binary ABI requirements; older distributions may need a source build.
- An x86-64-v2 CPU. Linux requires a GPU/driver supporting Vulkan 1.3, X11 or Wayland, and the system libraries listed below.
- For the Windows ZIP, Windows 10 or 11 x64 with a Vulkan 1.3 capable GPU and graphics driver.
- Python 3.12+ for local data preparation and the launcher.
- At least 4 GiB of free space for extracted data; 5 GiB recommended, with additional room for caches.
- A compatible controller; Xbox, PlayStation and Nintendo Switch prompt layouts are available. See [controls](controls.md).

The Linux runtime directly requires `libX11.so.6`, `libX11-xcb.so.1`, `libxcb.so.1` and `libwayland-client.so.0`, alongside glibc, libstdc++ and libgcc. Install both the listed X11 and Wayland client libraries even if your desktop uses only one protocol. A working system Vulkan loader and GPU driver are also required. The release’s `build-record.json` records the actual binary dependencies.

The Windows package includes the required Microsoft release CRT libraries and a self-contained ISO extraction helper; a separate Visual C++ Redistributable installation is not required. Python 3.12+ and your system Vulkan graphics driver are still required.

No universal minimum hardware specification has been established. Start at 720p and increase resolution after confirming normal gameplay speed.

## Supported data

The supported title ID is `454107DE`, media ID `022202E5`, XEX version `0.0.0.2`. Exact expected SHA-256 values are:

| Input | SHA-256 |
| --- | --- |
| USA disc image | `dc8ae0c22f3b95efc8b54cb5ff04e7682f9dc2785f54ecb6f489af7019dd0623` |
| `default.xex` | `5d583bc4c6a3a13085508a823eff4ebe676a0131ed7f2d5ccf2f14eb0e47332f` |

The authoritative record is `config/input-manifest.json` in the source, or `support/input-manifest.json` in a runtime package. Other editions are unsupported.

## First launch on Linux

Keep your original disc image separate from the package. From the Linux package directory, run:

```sh
./install.sh
```

The setup opens a file picker for your supported ISO when available, with a terminal fallback, and prepares a private local installation. It runs without administrator access or downloading game data. You can provide the path explicitly:

```sh
./install.sh --iso "/absolute/path/to/Fight Night Round 3 (USA).iso"
./launch.sh
```

Launching `./launch.sh` without a configured installation starts first-run setup, then opens the game. After setup, the launcher remembers the local data path. Extraction needs at least 4 GiB free; 5 GiB is recommended before allowing for caches.

## First launch on Windows

Extract the complete ZIP into a new folder. Install Python 3.12+ with the Python launcher or `python` on PATH, then run from PowerShell:

```powershell
.\install.cmd --iso "C:\Games\Fight Night Round 3 (USA).iso"
.\launch.cmd
```

You can also open `launch.cmd` directly; first launch offers setup when no installation is configured. Keep your original disc image separate from the package. The package does not download game data.

## Use an existing extraction

The data root must contain `default.xex` and the game's original directory structure. To select it explicitly:

```sh
./install.sh --game-data-root "/absolute/path/to/game-data"
./launch.sh --game-data-root "/absolute/path/to/game-data" --prepare-only
./launch.sh --game-data-root "/absolute/path/to/game-data"
```

On Windows, use the same options with the supplied command files:

```powershell
.\install.cmd --game-data-root "C:\Games\FNR3-data"
.\launch.cmd --game-data-root "C:\Games\FNR3-data"
```

`--prepare-only` verifies data and generates private frontend/glyph overrides without opening the game. It requires an explicit or remembered valid data path and does not start interactive setup. A normal launch also prepares overrides automatically and refreshes them when their inputs change. Do not rename an ISO to `default.xex`.

The default extracted-data directory is `${XDG_DATA_HOME:-~/.local/share}/fnr3/game-data`. The selected absolute path is remembered in `installation.json` under the user-data directory. An unrelated existing destination is not overwritten.

On Windows, the default extracted-data directory is `%LOCALAPPDATA%\fnr3\user\game-data`.

## Settings and updates

Open **OPTIONS → GRAPHICS**. Choose resolution, fullscreen, FXAA, texture filtering, controller family and action bindings. **SAVE** persists settings; **SAVE AND RESTART** applies them through the launcher. Returning without saving discards pending edits. Use the native footer's return action; there is no separate Back row.

Linux user data defaults to `~/.local/share/fnr3` and cache to `~/.cache/fnr3`, honoring `XDG_DATA_HOME` and `XDG_CACHE_HOME`. Windows defaults to `%LOCALAPPDATA%\fnr3\user` and `%LOCALAPPDATA%\fnr3\cache`. `--user-data-root` and `--cache-root` allow custom locations. Saves and settings live outside the package; back them up before an update.

Use a new directory for each package version, retain the same user-data paths, and launch through its supplied launcher. Do not copy old game-derived overrides into the release directory. See [troubleshooting](troubleshooting.md) and [known issues](known-issues.md) if loading, audio, text or controls misbehave.
