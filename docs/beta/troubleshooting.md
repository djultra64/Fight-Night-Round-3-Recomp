# Troubleshooting

## Unsupported game edition

Use the supported USA Xbox 360 release: title ID `454107DE`, media ID `022202E5`. The manifest in `config/input-manifest.json` records exact ISO/XEX hashes. A matching title alone is insufficient. Do not bypass the hash checks or mix files from different releases.

The extracted data directory must contain `default.xex` and the game's original directory structure. Pass an absolute path with `--game-data-root`; quote paths containing spaces.

## Setup reports an existing installation or lock

Setup does not overwrite an unrelated destination. Select the existing verified extraction or use a separate installation directory. Failed extraction normally cleans its own temporary stage and lock. If a crash leaves `.install.lock`, verify that no installation is still running before removing only that stale lock and retrying. Do not delete original data or user saves to bypass an installation error.

## The game will not start

Run the launcher from a terminal and retain the error. Check Python 3.12+, the supported data, a working Vulkan driver, X11 or Wayland, and the package's required system libraries. The packaged Linux binary requires glibc 2.38+ and libstdc++ with GLIBCXX_3.4.32 (GCC 13.2) or newer. A missing GLIBC/GLIBCXX symbol usually means the distribution is too old for that binary; use a compatible system or build from source. The build records list runtime dependencies; the package does not replace your graphics driver.

Use `--prepare-only` to isolate original-data verification and local frontend/glyph generation from game startup. If generated overrides are stale, rerun the launcher with `--regenerate-assets`. Keep your original game data intact.

## Settings do not persist or restart

Choose **SAVE** or **SAVE AND RESTART**. Returning from the page without saving discards pending changes. Graphics changes require a restart. Start through the supplied launcher; it handles the game's restart request.

The Linux defaults are `$XDG_DATA_HOME/fnr3` (otherwise `~/.local/share/fnr3`) for user data and `$XDG_CACHE_HOME/fnr3` (otherwise `~/.cache/fnr3`) for cache. Windows defaults are `%LOCALAPPDATA%\fnr3\user` and `%LOCALAPPDATA%\fnr3\cache`. Configuration is `port-settings.toml` and the runtime log is `runtime.log` under the user-data directory. Custom `--user-data-root` and `--cache-root` override these defaults. Back up saves before experimenting with user files.

## Performance or timing looks wrong

Start with 720p, the original game clock and Mailbox/VSync. Disable external frame caps and injected overlays while reproducing the issue. 900p and 1080p use the 1440p 2× render tier, so those output choices have similar rendering cost. Higher presentation counts do not prove faster game simulation. FXAA and texture filtering are available in GRAPHICS; original MSAA is read-only.

## Wrong controller prompt

Select the appropriate controller family in GRAPHICS if automatic identification is ambiguous. Check optional action remaps and compare the physical position with the [layout table](controls.md). Report both the displayed prompt and the action actually performed.

## Reporting a bug

Include beta version, OS, CPU/GPU and driver, controller/connection, graphics settings, matchup or menu sequence, expected behavior and what happened. Include whether it reproduces without overlays. For a more detailed runtime log, pass `--log_level=info` through the launcher. Review logs for personal paths before sharing. Do not upload your ISO, XEX, assets, saves containing private information, generated PowerPC sources or game-derived diagnostic dumps.
