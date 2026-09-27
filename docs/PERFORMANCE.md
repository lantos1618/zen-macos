# Desktop validation

Measured 2026-09-27 on Apple M2 Pro, macOS 26.6.2. These observations validate
integration and identify remaining limits; they do not guarantee sustained
60 FPS during speech inference. Reproduction commands and API contracts are in
[the SDK README](../README.md#display-pacing-and-threading). Portable capture
memory benchmarks have a separate [report](../benchmarks/RESULTS.md).

## Lifecycle and capture

Three 120-frame display-link lifecycle runs passed with 120 updates each and
no coalescing. The seven-tick deadline fallback took 0.101134 seconds. The final
allocation-budget sweep passed 241 failure paths and 271 successful double
closes. This checks cleanup behavior, not native heap leaks; CoreAnalytics
emitted two context-leak diagnostics during an earlier allocation sweep.

Microphone start, FFT activity, and stop were checked in Zen Code. Fresh-denial
permission UI and denied-to-authorized recovery have not been UI-tested.

## Pacing

| Desktop run | Result |
| --- | --- |
| Two 360-frame windows | 60 submission FPS; p95 17.05/17.10 ms, p99 32.96/32.84 ms |
| Third window | Fifteen-second deadline reached at 349 frames; roughly one-second p99 |
| Separate steady window | Deadline reached at 164 frames; 171 updates, seven coalesced, p95 1016.57 ms |
| Steady run's independent fallback | Passed, 0.101112 seconds |

No microphone or model inference ran in these SDK diagnostics. Keep the window
foreground when measuring active pacing: occluded/background windows may be
throttled. Submission intervals do not measure physical presentation or full
Core Animation compositor cost. The cause of every deadline failure has not
been established.

## Trace correlation

A bounded Metal System Trace recorded the process foreground from 1.269 to
2.839 seconds, then background until 11.089 seconds. Submissions fell from 42
in the partial first second and 50 in the transition second to roughly three
per second afterward. GPU clear durations were 19.4 µs median, 22.1 µs p95,
and 23.9 µs maximum; CPU-to-GPU latency was 0.589 ms median, 0.966 ms p95,
and 1.933 ms maximum. No drawable-buffer-wait rows were recorded.

This associates that run's slowdown with background state rather than costly
GPU clears. It does not explain every prior failure or the app's separate
first-inference dip. The recording ended at its time limit; xctrace reported a
backdated-signpost warning and saved a readable trace. Raw system traces remain
local ignored build artifacts.
