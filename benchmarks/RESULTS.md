# Measured baseline

Append 256 float32 samples to the production capture state, then discard 256 while retaining 160000 samples (10 seconds). Every iteration shifts the retained 640 KB prefix. This intentionally stresses discard frequency; real segmented consumers discard less often.

Measured 2026-09-27T05:10:14.197889+00:00 on Apple M2 Pro (arm64).
macOS-26.6.2-arm64-arm-64bit

Compiler: `/Users/lyndon/zen-dev/zen/zen`; SHA-256 `5688b03fceaf54fa1a9cb675c25260e1402c47247e9996ba7c51122aa676a285`.
Library SHA-256: `e131f4975de8d597c73fadb29bd573c087d0dbcd775ec47f5cf54e1f54e0b13d`.
Apple clang version 17.0.0 (clang-1700.6.4.2) / Target: arm64-apple-darwin25.6.0 / Thread model: posix / InstalledDir: /Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/bin

| CFLAGS optimization | Samples | Median µs/iteration | p95 µs/iteration | Median of 16.67 ms frame budget |
|---|---:|---:|---:|---:|
| -O0 | 93 | 446.044 | 458.953 | 2.676% |
| -O2 | 93 | 15.444 | 16.240 | 0.093% |

Background workload: Existing user apps remained running; app builds and native inference benchmarks were paused during this rerun.

Each sample is a 1000-iteration batch mean, not a single-call latency. Each of 3 processes warms 1000 iterations, then reports 31 batches. p95 is nearest-rank over the combined batch means.
Timed sections allocate no buffers and print only after each batch. A checksum and validity checks keep results observable.
The live app was not stopped. These measurements are from a shared desktop and are not a real-time guarantee. They exclude device capture, GPU presentation, model inference, actor transport, and end-to-end UI latency.

Reproduce: `python3 benchmarks/run.py --zen ../zen/zen`.
Exact compiler argv, raw batches, metadata, and JSON results are in ignored `build/benchmarks/`.
