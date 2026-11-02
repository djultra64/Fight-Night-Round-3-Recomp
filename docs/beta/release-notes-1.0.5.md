# Version 1.0.5

Project work: **djultra64**.

A regular Windows and Linux release addressing the reproduced Dodge / Mickey Ward career loading crash reported in [issue #2](https://github.com/djultra64/Fight-Night-Round-3-Recomp/issues/2). Compatibility testing remains ongoing.

## Changes

- Correct a collision-plane comparison where floating-point roundoff could make the original angle calculation return NaN, overfill local grouping arrays and overwrite the guest stack.
- Prevent a second reproduced native-1080p loading failure by returning 13 MiB of excess canvas reservation to the asset heap. Internal rendering remains 1920×1080 at the 1080p preset; no resolution or quality reduction is used.
- Add regression tests for both causes and guards against generated-call-site drift.

## Validation and remaining work

We reproduced the reported stack-write failure using an artificial career profile, then verified the corrected Windows executable through loading, Ward combat, Pause/Settings/Resume, knockout results, return to Career Central and an original-writer save. This is a targeted fixture, not a full career playthrough. The Windows suite passed 323 tests. A bounded process-specific audio capture contained signal with no capture discontinuities.

Matched menu timing samples did not show a sustained cadence regression. Guest-swap timings are CPU-side observations, not display FPS. The combat-to-results trace still contains frame-time spikes; this release does not certify sustained 60 FPS. One initial-loading hang was observed and remains unresolved. Career-preview stutters, complete career testing and other intermittent loading/audio reports remain under investigation. See [detailed validation](../issue-2-validation.md) and [known issues](known-issues.md).

The Linux package contains the same source changes; the artificial-career gameplay validation described above was performed on Windows.

## Installation

Download the Linux archive or Windows ZIP, extract into a new folder and use the supplied launcher. Existing saves, settings and caches remain in their user-data directories. Python 3.12+ and user-owned supported USA game data are required. See [installation](installation.md).

No original game assets or private diagnostic probes are included. Third-party notices and licenses remain intact.
