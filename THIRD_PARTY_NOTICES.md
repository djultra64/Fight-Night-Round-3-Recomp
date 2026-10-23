# Third-party notices

Project work: **djultra64**.

This document is a notice index, not a replacement for any dependency's license. Preserve the complete license and copyright texts shipped with the relevant source or package.

## ReXGlue and Xenia

The project uses [ReXGlue](https://github.com/rexglue/rexglue-sdk), pinned to `f5337cdc947ff6d4c4196737e2c807a48f2a1fc2`, with project patches. Its license is preserved in [patches/ReXGlue-LICENSE](patches/ReXGlue-LICENSE).

That notice credits Tom Clay and identifies portions derived from Xenia, copyright Ben Vanik and Xenia project contributors. Those authentic credits and required terms remain in force.

## SDK dependencies

ReXGlue includes dependencies such as SDL, FFmpeg, Vulkan components, glslang, SPIR-V Tools, Vulkan Memory Allocator, libmspack, fmt, spdlog, xxHash and other libraries. They retain their respective authorship and licenses. Consult the pinned SDK source and the package's `licenses/` tree for the complete texts applicable to the actual build. Build records identify the verified SDK and dependency revisions.

The package builder copies license, copying and notice files from the pinned SDK dependency tree. Dependency obligations must be reviewed for the actual distributed artifacts; this index does not claim a single license covers all components.

## extract-xiso

The optional local ISO setup uses extract-xiso. Preserve its complete license and required acknowledgment:

This product includes software developed by in <in@fishtank.com>.

## Windows runtime and ISO helper

Windows packages include the imported Microsoft Visual C++ Release runtime libraries from the Visual Studio redistributable directory. They remain copyright Microsoft Corporation and retain their applicable license terms. The package includes a Microsoft runtime notice and records the distributed files and hashes.

The Windows ISO helper also uses the upstream Win32 getopt and directory compatibility code. Complete original notices are included with the Windows package, including the Apache Software License 1.1 and Kevlin Henney’s directory implementation notice.

This product includes software developed by the Apache Software Foundation (http://www.apache.org/).

## Original game

Fight Night Round 3, its original executable, assets, trademarks and other game content belong to their respective rights holders. They are not licensed by this project. Users supply their own supported original data; no ISO, XEX, generated PowerPC source files, or extracted/game-derived asset files are included in the public distribution. The runtime binary contains compiled translated game code.

The project’s own original code is licensed under [BSD-3-Clause](LICENSE), copyright 2026 djultra64. That license does not cover third-party components or original game content.
