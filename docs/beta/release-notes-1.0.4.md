# Version 1.0.4

Project work: **djultra64**.

This is a regular Linux and Windows release with rendering/UI corrections and targeted stability fixes. Compatibility testing remains ongoing.

## Changes

- Match every resolution preset to its internal rendering dimensions: 720p, 900p, 1080p, 1440p, 1800p and 2160p.
- Fit intro videos to the fullscreen canvas and correct menu text, HUD primitives, demo-mode text and bloom/scissor placement at native resolutions.
- Fix a reproduced native-1080p Windows pause-menu freeze by balancing physical-memory budgets while preserving allocator ownership.
- Correct specific Vulkan submission-completion, readback retirement, attachment metadata, scratch-buffer usage, EDRAM ordering, presentation-resource retirement, rendering dependencies and vertex-residency defects.
- Preserve valid late XMA audio continuations across relative frame-header/successor boundaries.
- Add the actively-maintained badge and roadmap to the README.

## Validation and remaining work

The underlying changes passed 394 Windows contracts. A bounded Windows1080p run exercised menus, repeated Pause/Resume, career contracts/training, a three-round fight, results/save and CREATE CHAMP STYLE without an observed physical-heap/device-loss/access-violation failure. These observations do not establish complete compatibility.

Opponent-preview stutters remain reproducible. Full career testing, all-preset UI coverage and sustained 60 FPS/frame-time validation are still ongoing. Intermittent loading, crash, text and audio reports remain under investigation. See [known issues](known-issues.md).

## Installation

Download the Linux archive or Windows ZIP, extract into a new folder and use the supplied launcher. Existing saves, settings and caches remain in their user-data directories. Python 3.12+ and user-owned supported USA game data are required. See [installation](installation.md).

No original game assets or private diagnostics are included. Third-party notices and licenses remain intact.
