# Known issues — beta 0.7

Beta 0.7 targets the original approximately 30 FPS game clock. Complete game compatibility and uninterrupted play are not guaranteed.

| Area | Current limitation |
| --- | --- |
| Fights and loading | Loading can stall or fail. Compatibility can vary between matchups and game modes. |
| Audio | Silence, interrupted playback and audio-related loading problems can occur. |
| Text | Save/load text can disappear intermittently. |
| Performance | Higher resolutions increase GPU cost. No universal minimum hardware specification is available. |
| Cuts/healing | Close-up hand movement can slow down. |
| Controllers | Automatic family identification can be ambiguous. Use manual selection and optional action bindings if prompts or controls do not match your device. |

## Graphics and timing

900p, 1080p and 1440p share the 2× render tier. Selecting a lower output resolution within that tier may not reduce GPU cost. Original MSAA is read-only.

Experimental 60 FPS, interpolation and the alternative native renderer are outside the production target. Display presentation counters do not measure original game simulation speed. Disable external frame caps and injected overlays when troubleshooting timing or rendering issues.

See [troubleshooting](troubleshooting.md) for startup, settings and controller issues.
