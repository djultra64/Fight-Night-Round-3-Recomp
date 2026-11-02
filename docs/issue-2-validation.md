# Dodge / Mickey Ward loading crash

Work: djultra64. Windows investigation, 2026-11-02 UTC.

The artificial pre-fight profile reproduced the published v1.0.4 access
violation writing guest address `0x70190000`, matching issue #2's report.
It is a targeted fixture, not evidence of a naturally completed career:
the original amateur record and some amateur state remain in the profile.

## Causes and changes

1. In collision-plane grouping, float-normalized planes can have a dot product
   one float ULP outside `[-1, 1]`. The original `acos` returns NaN, duplicate
   planes become separate groups, and the fixed local arrays overflow.
   Repair only overshoot within four float ULPs at the exact plane-comparison
   call site. Keep the original `acos`, valid inputs and larger invalid inputs.
   The build transform rejects missing, duplicate or already patched anchors.
2. After fixing geometry, the 1080p fixture exposed a failed 14.6 MiB asset
   allocation while loading trainer textures. Eight padded native canvas
   planes need 35 MiB more than the original canvas, but rounding reserved
   48 MiB. Root growth is capped independently, so this consumed space needed
   by the sibling asset heap. Round the allowance up to one MiB instead:
   1080p reserves 35 MiB and 900p reserves 17 MiB. Preserve the root cap,
   original allocator margin, preset dimensions and resolution scales.

## Verification

- Native Windows regressions failed before each change and passed afterward.
  The complete Windows Python suite passed 323 tests with zero skips, failures
  or errors. The compiled graphics policy contract also passed.
- An observational geometry run returned with eight groups and no invalid
  comparison angles. Private probes were removed from the final executable.
- With original assets and published runtime DLLs, the combined executable
  loaded Dodge / Madison Square Garden against Ward at internal 1920×1080,
  entered combat, opened pause/settings, resumed, reached a knockout result,
  returned to Career Central, and saved through the original writer. All three
  post-fight MC02 checksums validated.
- A process-specific 29.99-second, 48 kHz stereo audio capture around the
  intro/combat transition had no capture discontinuities and no completely
  silent one-second blocks. This does not establish whole-session continuity.

## Performance evidence and remaining limits

Every run retained available frame intervals and failures. The timing source
is **guest swap routine entry**, including CPU command preparation; it is not
GPU completion, display FPS, or proof of unique presented frames. Runs used
1080p, Vulkan, INFO logging, no readback, identical assets/profile, full interval
capture and fresh application caches. Driver cache state was not controlled.

| 60-second Career Central window | Guest swap Hz | p99 ms | Maximum ms |
| --- | ---: | ---: | ---: |
| Published reference 1 | 59.3900 | 17.7524 | 18.8658 |
| Combined changes, run 12 | 59.3932 | 18.1939 | 20.7358 |
| Combined changes, run 14 | 59.3989 | 17.7146 | 18.4622 |
| Published reference 2 | 59.4097 | 17.7252 | 18.1666 |

These observations do not establish a sustained menu regression or certify
60 displayed FPS. Keep the slower first candidate window in the record.
The run-14 combat-to-knockout/results window averaged 45.4779 guest swaps/s,
with p99 35.4197 ms and a 467.5466 ms maximum; it is a mixed transition window,
not a continuous-combat benchmark and not an accepted performance result.

One combined-build run remained on initial loading for 283 seconds and was
closed normally; the next identical run booted successfully. That intermittent
startup hang remains unresolved. Full-career testing, sustained combat timing,
display-frame validation and the project's 60 FPS acceptance gate remain open.
This targeted fix is not a release-wide stability or performance approval.
