# Known issues — beta 0.7

Beta 0.7 preserves the original approximately 30 FPS game clock. The accepted Linux baseline runs on the ROG Ally, reaches the ring and accepts gameplay input. It does not establish full compatibility or a complete fight without interruption.

| Area | Current limitation |
| --- | --- |
| Fights and loading | Earlier builds exposed missing callbacks and loading failures. Corrections allowed the tested matchup to reach the ring, but a complete fight and every matchup remain unverified. |
| Audio | Ring audio has been confirmed. Silence and loading problems have recurred in testing. XMA pacing, drain and split-header fixes have automated regressions, but prolonged playback and looping remain unverified. |
| Text | Save/load text has appeared and disappeared within a session. The intermittent cause has not been established. |
| Performance | Normal-speed gameplay around the original 30 FPS target has been observed. No universal minimum or measured gain per patch is claimed. Higher resolutions can reduce performance. |
| Cuts/healing | A reported slowdown during close-up hand movement appeared improved in a later session, but has not been confirmed across longer tests. |
| Menu sounds | Original navigation sound calls are restored; audibility still needs confirmation. |
| Controllers | The integrated Ally controls work in user testing. Full physical prompt/action verification for separate Xbox, PlayStation and Switch controllers remains pending. |
| Windows | Source support is prepared. A current Windows build, runtime package and gameplay session have not been validated. |

## Confirmed behavior

On the Linux/Ally baseline, the native GRAPHICS page, QUIT GAME, saving 1080p with SAVE AND RESTART, and returning from GRAPHICS to OPTIONS have been confirmed. The launcher handles the reserved restart exit code and relaunches the game with the same user-data paths.

The user confirmed normal-speed 2× rendering at 1080p with Mailbox presentation and no visible tearing in that test. This observation is specific to that setup and session. GPU presentation counters alone do not measure original game simulation speed.

## Outside the beta target

Experimental 60 FPS, interpolation and the alternative native renderer are not production features. A display overlay showing 60 presentations per second does not establish a correctly timed 60 FPS game. Keep external frame caps and injected overlays out of the initial troubleshooting baseline: an earlier overlay session ended inside MangoHud.

Automated tests and package audits check specific contracts. They do not certify long fights, audio stability, every controller or Windows compatibility.
