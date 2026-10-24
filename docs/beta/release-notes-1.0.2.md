# Fight Night Round 3 Recomp 1.0.2

Project work: **djultra64**.

## Changes

- Fixed saved custom boxer hair colors appearing black in boxer selection and combat. The original color bake now reads back only the textures needed by its CPU compressor, without enabling full-scene readback during gameplay. Existing saves do not need to be edited or recreated.
- Fixed scaled texture readback exceeding Vulkan storage-buffer limits at higher resolutions, including 2160p.
- Added **FRAME RATE: 30 FPS / 60 FPS** in **OPTIONS → GRAPHICS**. The default is 60 FPS. Choose **SAVE AND RESTART** to apply a change; **SAVE** applies it on the next launch.
- Retained the original-speed timing and replay slow motion of the existing 60 FPS mode, controller prompts and the 1.0.1 guest callback crash correction.

## Install or update

Download the Linux archive or Windows ZIP and extract it into a new folder. Use the included launcher. Existing saves, settings and caches remain outside the package. If asked, provide your supported USA ISO or use `--game-data-root` with an existing verified extraction. No original game assets are included.

Both runtime packages use Vulkan. See [installation](installation.md) for requirements and [known issues](known-issues.md) for remaining compatibility limitations.
