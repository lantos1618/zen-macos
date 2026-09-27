# Zen hot-loop baseline

Run on macOS with an available Zen compiler:

```sh
python3 benchmarks/run.py --zen ../zen/zen
```

The hot loop and monotonic timing are Zen. Python creates a temporary build
project, records compiler arguments, runs three fresh processes per build,
and computes median/p95 over 93 batch means. Each batch contains 1000
iterations; each process first warms 1000 iterations. `--runs N` changes the
number of processes. No microphone, permission prompt, window, or live-app
restart is involved.

Both explicit `-O0` and `-O2` builds use the same source and inputs. The build
system's initial `-O2` is overridden by later CFLAGS; exact Clang argv are
recorded so the selected optimization can be verified. These are optimized
and unoptimized baselines, not claims about the project's default flags.

Caller-owned working buffers are allocated before timing. Results include a
checksum and validation checks. Batch timing excludes output, initialization,
model inference, actor transport, GPU presentation, and end-to-end latency.
The reported p95 describes batch means, not single-operation tail latency.
The 60 Hz comparison is a reference 16.67 ms budget, not measured frame rate.

`RESULTS.md` records the measured machine/compiler, workload, and caveats.
Raw logs, exact build arguments, and machine-readable results go to ignored
`build/benchmarks/`. `ZEN_BENCH_CPU` can supply a separately verified CPU model
when sandbox policy blocks the read-only sysctl query.
