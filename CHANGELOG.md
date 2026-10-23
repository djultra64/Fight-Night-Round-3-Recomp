# Changelog

## 1.0

- Notification-driven Linux multi-object waits remove fixed polling latency while retaining abandoned-lock recovery.

- Fixed idle shader-cache flushing and moved periodic driver-cache persistence off the GPU submission thread.
- Fixed a race when retiring texture invalidation watches.
- Added native 60 FPS gameplay with original gameplay speed and stock-rate 30 FPS intros.
- Added fractional crowd animation advancement and 60 FPS replays with elapsed-time updates that preserve slow motion.
- Included Vulkan runtime packages for Windows and Linux with persistent shader/pipeline caching, parallel compilation and cached complete-pipeline prewarming. Previously unseen content can still trigger compilation stalls.
- Retained first-launch ISO import, native graphics settings, saved settings, SAVE AND RESTART, QUIT GAME and controller family prompts with optional action remapping.
- Updated release documentation for phase-specific timing, GPU headroom and remaining compatibility limitations.

See the [1.0 release notes](docs/beta/release-notes-1.0.md).

## 0.7 — public beta

- Added the native Windows Vulkan runtime package, release CRT libraries and local ISO setup.
- Removed redundant mouse-capture UI work while polling keyboard input.
- Added the native GRAPHICS page with unified resolution, fullscreen, FXAA and texture filtering settings.
- Integrated QUIT GAME, saved settings and launcher-managed SAVE AND RESTART.
- Added Xbox, PlayStation and Nintendo Switch prompt families, automatic device tracking, manual selection and 14 optional action bindings.
- Preserved the original approximately 30 FPS game clock, with Linux Vulkan Mailbox/VSync presentation and persistent shader caching.
- Added verified local asset preparation, a pinned patched SDK build and audited packages without original game data.
- Added installation, build, controls and troubleshooting documentation with current compatibility limitations.

See the [0.7 release notes](docs/beta/release-notes-0.7.md). Earlier local experiments are not supported production releases.
