# Fight Night Round 3 Recomp 1.0.3

Project work: **djultra64**.

## Changes

- Improved startup and rendering consistency: Vulkan draws wait for the pipeline they need, and completed graphics state is published together. Cached pipelines prepare in the background while the game continues loading.
- Fixed window resolution being multiplied by desktop scaling. The selected size now stays in physical pixels across monitor selection, density changes, resizing and fullscreen restoration.
- Fixed graphics task dispatch synchronization and the lifetime of render targets used by background pipeline compilation.
- Fixed OPTIONS reopening as an empty TITLE TEXT screen after leaving and returning to the menu.
- Save the active profile after confirming a custom boxer in CREATE CHAMP, including edits to an existing boxer. Storage failures offer Retry or Continue Without Saving.
- Keep a separate runtime log and exit record for every launch and intentional restart. The new `--diagnostics` option adds startup details and optional Windows crash dumps.
- Retained native 30/60 FPS selection, controller-family prompts, action remapping and existing saves and settings.

Thanks to **fransisigoswho** for reporting the intermittent startup, missing rendering and desktop scaling issues in 1.0.2. Your report helped guide this release.

## Install or update

Download the Linux archive or Windows ZIP and extract it into a new folder. Use the included launcher. Existing saves, settings and caches remain outside the package. If asked, provide your supported USA ISO or use `--game-data-root` with an existing verified extraction. No original game assets are included.

Both runtime packages use Vulkan. See [installation](installation.md) for requirements and [known issues](known-issues.md) for compatibility information.
