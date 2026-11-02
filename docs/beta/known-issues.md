# Known issues — 1.0.5

Version 1.0.5 uses native 60 FPS gameplay while preserving original gameplay speed. Intros retain their stock 30 FPS cadence, crowd animation uses fractional advancement, and replay updates use elapsed time to preserve slow motion. Complete game compatibility and uninterrupted play are not guaranteed.

| Area | Current limitation |
| --- | --- |
| Fights and loading | Intermittent loading stalls and crashes remain under investigation. Compatibility can vary between matchups and game modes. |
| Career / CREATE CHAMP | Full career testing is ongoing. Loading or repeatedly switching opponent previews can produce visible stutters, including with a warm cache. |
| Audio | Silence, interrupted playback and audio-related loading problems can occur. |
| Text | Save/load text can disappear intermittently. |
| Performance | A steady 60 FPS requires enough CPU/GPU headroom. Higher resolutions increase GPU cost; no universal minimum hardware specification is available. |
| Shader/pipeline compilation | Persistent caches, parallel compilation and cached complete-pipeline prewarming reduce repeat work. Previously unseen content can still compile during play and cause frame-time spikes. |
| Cuts/healing | Close-up hand movement can slow down. |
| Controllers | Automatic family identification can be ambiguous. Use manual selection and optional action bindings if prompts or controls do not match your device. |

## Graphics and timing

Presets match their internal rendering dimensions from 1280×720 through 3840×2160. UI/video corrections were checked in bounded native-1080p Windows scenarios; complete all-preset and cross-platform coverage is ongoing. Original MSAA is read-only. Selecting 2160p does not guarantee a steady 60 FPS.

The production target uses phase-specific native timing. Earlier simple frame-rate unlocks, interpolated presentation experiments and the alternative native renderer are outside this release. Display presentation counters alone do not establish correct game timing or smooth frame pacing. Disable external frame caps and injected overlays when troubleshooting timing or rendering issues.

See [troubleshooting](troubleshooting.md) for startup, settings and controller issues.
