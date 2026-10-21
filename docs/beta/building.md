# Building from source

The production build compiles the host, patched ReXGlue runtime and Xenos GPU plugin together. Linux uses Vulkan; Windows automatically selects Direct3D 12. It generates game-specific code locally from your verified XEX. It does not require or distribute pre-generated PowerPC sources.

## Prerequisites

Use an x86-64 Linux system with Python 3.12+, Git, CMake 3.25+, Ninja, LLVM/Clang 18+ and a Vulkan development/runtime environment. The Flatpak build route uses `org.freedesktop.Sdk//25.08` and its LLVM 20 extension. Python 3.12+ is required for safe archive extraction.

Windows source support expects an x64 developer terminal with the MSVC build environment, Python 3.12+, Git, CMake, Ninja, LLVM/Clang including `llvm-readobj`, and the Windows SDK. The separate ISO extraction helper requires an x86-64 MinGW-w64 C compiler, such as GCC or Clang from MSYS2 UCRT64. The game and SDK continue to use native LLVM with the MSVC environment. `--target` does not enable cross-compilation.

## Prepare the inputs

Keep the supported game extraction in `assets/`, with `assets/default.xex` matching `config/input-manifest.json`. Do not commit this directory or any generated game resources.

Clone and initialize the pinned SDK from the project root:

```sh
git clone https://github.com/rexglue/rexglue-sdk.git .cache/rexglue-source
git -C .cache/rexglue-source checkout --detach f5337cdc947ff6d4c4196737e2c807a48f2a1fc2
git -C .cache/rexglue-source submodule update --init --recursive
```

Also clone the pinned ISO extraction tool. Packaging requires this source checkout even when you already have extracted game data:

```sh
git clone https://github.com/XboxDev/extract-xiso.git .cache/extract-xiso
git -C .cache/extract-xiso checkout --detach 3f5b62cfe68f000b0e3c8a30104973f3a297948e
```

If you need to extract your own supported ISO into the source tree, first build the tool and extract into a new `assets/` directory:

```sh
cmake -S .cache/extract-xiso -B build/iso-extractor/linux-amd64 -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_POLICY_VERSION_MINIMUM=3.5
cmake --build build/iso-extractor/linux-amd64 --target extract-xiso
./build/iso-extractor/linux-amd64/extract-xiso -x "/absolute/path/to/Fight Night Round 3 (USA).iso" -d assets
```

These extraction commands use your native Linux CMake/Ninja toolchain. The extracted `assets/default.xex` must match the [supported SHA-256](installation.md#supported-data); the production build checks it before generation. Keep the extraction private. The packaged `install.py` depends on its package's support files and is not a source-checkout preparation command.

The build verifies the SDK revision, submodule revisions and tracked-file cleanliness. The extractor build likewise verifies its pinned source revision and tracked-file cleanliness. It applies the project's patches to an isolated source export under `.cache/production/`. A prebuilt SDK without these patches is not a substitute.

## Linux

```sh
python3 tools/port_build.py build --flatpak --jobs 2
python3 tools/port_build.py package --dry-run
python3 tools/port_build.py package
```

For an appropriately configured native toolchain, omit `--flatpak`. The build does not launch the game. Outputs are under `build/production/linux-amd64/`; the default package is `dist/fight-night-round-3-recomp-v0.7-beta-linux-amd64/`. Choose a new output directory with `package --output /absolute/path/to/new-package`; existing package destinations are rejected.

## Windows

The recipe compiles both renderer backends and automatically selects Direct3D 12 for the production runtime. No user backend setting is required.

From the x64 developer terminal:

```powershell
py -3 tools/port_build.py build --jobs 2 --extractor-compiler "C:\msys64\ucrt64\bin\clang.exe"
py -3 tools/port_build.py package --dry-run
py -3 tools/port_build.py package
```

The compiler path above is an example. Set `--extractor-compiler` to your installed MSYS2 UCRT64 `gcc.exe` or `clang.exe`, or an equivalent MinGW-w64 C compiler targeting x86-64. The build validates the compiler target; this option applies only to the ISO helper.

Output directories are `build/production/win-amd64/` and `dist/fight-night-round-3-recomp-v0.7-beta-win-amd64/`. The helper statically links its compiler runtime. Windows packages also include the required Microsoft release CRT libraries from the approved Visual C++ Redistributable source.

## Verify and package

```sh
python3 -m unittest discover -s tests -p test_port_build.py
```

The package audit verifies recorded artifact hashes, runtime/plugin completeness and load paths, and rejects original game data. Packages preserve build records and dependency notices. The recipe records source inputs and compiler details; it does not promise identical binaries across different toolchains. Game compatibility remains subject to the [known issues](known-issues.md).

Keep SDK revisions and patches aligned. If verified isolated sources change, investigate the discrepancy before removing only the affected isolated production directory and rebuilding. Never replace the SDK pin or bypass input verification merely to make a build pass.
