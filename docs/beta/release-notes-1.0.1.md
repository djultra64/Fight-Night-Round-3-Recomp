# Fight Night Round 3 Recomp 1.0.1

Project work by **djultra64**.

## Crash correction

This update fixes a diagnosed crash during gameplay when the game called an original indirect callback that had not been compiled into the port. The crash was identified at guest callback `0x8234A348`. The affected family contains 26 small virtual-dispatch wrappers; automatic discovery had found only the first. The build now explicitly includes the remaining 25 original wrappers, preserving their virtual-table targets and calling behavior.

The correction is included in both the Linux and Windows Vulkan runtime packages. The native 60 FPS timing, resolution options, frame-pacing changes and shader-cache behavior from 1.0 are retained.

## Updating

Download the package for your operating system from [GitHub Releases](https://github.com/djultra64/Fight-Night-Round-3-Recomp/releases/tag/v1.0.1) and extract it into a new folder. Run `install.sh` on Linux or `install.cmd` on Windows to import your supported USA ISO, then use `launch.sh` or `launch.cmd`. Keep your previous installation until the new one is ready, and preserve your existing saves and settings. Python 3.12+ is required.

The packages do not contain an ISO or extracted game assets. Source builds generate the game-specific code locally from verified inputs.

## Remaining limitations

This addresses the identified missing-callback crash; it does not establish that every freeze or crash had the same cause. Intermittent loading, audio and text issues remain under investigation. This update does not add unverified replay or score-screen button notices and does not claim to fix postfight narration. See [known issues](https://github.com/djultra64/Fight-Night-Round-3-Recomp/blob/v1.0.1/docs/beta/known-issues.md) and the [installation guide](installation.md).
