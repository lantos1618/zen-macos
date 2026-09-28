# Bounded voice playback tests

Run from the workspace root on a Mac with the Apple SDKs:

```sh
python3 zen-macos/tests/voice_output/run.py --ios-sdk
python3 zen-macos/tests/voice_output/run.py --negative-control prefill
python3 zen-macos/tests/voice_output/run.py --negative-control fade
```

The runner checks both native adapters and the shared `zen-audio/src/playout.zen`
logic by appending `state.zen` to freshly read platform source and loading a
fresh copy of the production playout module in a temporary directory. It does not copy the
implementation into the repository fixture. No microphone permission, native
queue startup, sound output, or device installation occurs.

Checks cover four-packet startup prefill; initial and recovery fade-in;
underflow fade-out; sustained silence without repeated underflow counts;
recovery prefill; FIFO preservation through ring wrap; bounded overflow that
preserves pending samples; null/incorrect-length packets; and idle teardown.
Native start/callback paths remain reachable for compilation. Optional
`--ios-sdk` checks generated code against the physical iPhone arm64 SDK.

Negative controls must compile, then exit with a failed assertion: one changes the shared module to start
playback prematurely; the other removes its fade-in. A compiler failure or crash is
not accepted as a successful negative control.

Defaults use `zen-actor-runtime/zen` and its sibling `src`. Override with
`--zen /absolute/path/to/zen --std /absolute/path/to/src`. Python is test
orchestration only; playback implementation and synthetic assertions are Zen.
These tests do not establish audible quality or measure real device latency.
