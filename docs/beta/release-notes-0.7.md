# Fight Night Round 3 Recomp — beta 0.7

**Prerelease · Project work by DJ Ultra 64 — djultra64**

Beta 0.7 targets normal-speed play at the original approximately 30 FPS game clock. Linux has been built and tested on the ROG Ally. Windows support is prepared in source and remains unvalidated.

## Included

- Native OPTIONS → GRAPHICS integration and QUIT GAME.
- Unified 720p, 900p, 1080p, 1440p, 1800p and 2160p output selection, fullscreen, FXAA and texture filtering. Original MSAA remains read-only.
- Mailbox/VSync presentation and persistent shader caching.
- Saved settings and launcher-managed SAVE AND RESTART.
- Xbox, PlayStation and Nintendo Switch prompt families, automatic last-device tracking, manual family selection and 14 optional action bindings.
- Local frontend/glyph generation from verified user-owned assets.
- Source builds with a pinned, patched ReXGlue SDK and artifact/package audits.

## Validation and limits

The user confirmed Linux/Ally navigation, QUIT GAME, saving and restarting at 1080p, returning from GRAPHICS to OPTIONS, functioning Ally input and normal-speed Mailbox gameplay in the observed session. The native footer handles returning; there is no additional Back row.

A complete fight, prolonged stable audio, every physical controller family and Windows remain unverified. Intermittent loading, text and audio issues have occurred. See [known issues](known-issues.md) for the limits of the available evidence. Tests verify specific contracts and do not establish full playability.

Experimental 60 FPS, interpolation and the alternative native renderer are excluded from the production target. The output resolution selector does not promise performance at every setting; 900p, 1080p and 1440p share the 2× render tier.

No ISO, XEX, generated PowerPC source files or extracted/game-derived asset files are distributed. The runtime binary contains compiled translated game code. Supply the supported USA edition and follow [installation](installation.md). Dependencies retain their own credits and licenses.

The local installer was validated against the supported USA disc image: all 1,856 extracted files matched the existing verified extraction byte for byte (3,401,168,889 bytes). This verifies import integrity; that check did not open the game. Exact supported ISO and XEX hashes are listed in the [installation guide](installation.md#supported-data).
