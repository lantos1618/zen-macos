# Zen macOS

A native Apple-silicon macOS app written in current Zen. It opens a resizable,
Retina-aware Metal window, keeps a bounded UTF-8 input buffer in Zen, and speaks
entered text using AVFoundation. Native bindings, callbacks, and application logic are implemented in Zen.

## Build and run

Requires macOS 13+, Apple silicon, Xcode command-line tools, and the sibling
`zen` checkout with source-level native bindings.

```sh
cd ../zen
make build
cd ../zen-macos
ZEN_STD=../zen/src ../zen/zen build .
open app/ZenConsole.app
```

Type into the window. Backspace removes a UTF-8 codepoint. Enter speaks the
buffer using the system voice. Escape or the window close button exits.
Speech synthesis does not record microphone input.

For a bounded window/GPU smoke run:

```sh
app/ZenConsole.app/Contents/MacOS/ZenConsole --smoke
```

A successful smoke run reports rendered Metal frames. Run in a desktop session:
a restricted sandbox may prevent WindowServer/Metal access.

## Use the SDK from an app

[Zen Code](https://github.com/lantos1618/zen-tui) is an application that depends
on this SDK. Its app entry owns application text and configuration, while window, input, GPU presentation,
and speech implementation stay here. Register `../zen-macos/src/macos.zen` as
`b.lib("macos", { src: ..., libs: ["objc"], paths: [] })` in the app's build graph,
then list that library in the executable's dependencies. The executable uses
`language: "objective-c"` and the AppKit, Foundation, QuartzCore, Metal, and
AVFoundation frameworks. The dependency name becomes the import namespace;
no source copies or symlinks are needed.

```zen
App, Config = macos

main = (env: Env) Res<i32, AllocError> {
    arena ::= env.mem.alloc();
    app ::= App.configured(arena, Config(
        title: "My Zen App",
        heading: "MY WORKSPACE",
        description: "Type below. Enter speaks. Escape closes.",
        prompt: "you › ",
        greeting: "Welcome to my app."
    )).try();
    app.run(env)
}
```

Configuration text is borrowed and must remain valid through `run`.
`App.open(arena, title)` supplies the SDK demo's default copy. `run` closes
native resources on success or allocation failure. If an opened app is never
run, call `close`; repeated `close` calls are safe. Keep the caller's allocator
alive until closing: it owns the input storage. Do not copy live `App` values;
the current language does not enforce unique ownership of native handles.

## App-owned editing and close requests

Set `Config.editable: true` to own text editing. After each `App.tick(a)`, call
`take_key()` before the next tick. It returns an optional `KeyEvent` containing
native `code: u16`, `command: bool`, `shift: bool`, and UTF-8 `text: str`. Text
borrows the app's keyboard storage until the next tick; copy it before keeping
it or sending it to another thread. The slot is cleared each tick, and text
above 1,024 bytes per native event is ignored. This is bounded key delivery,
not a text editor or a complete native text-input/IME implementation.

In editable mode Enter, Backspace and Escape are forwarded instead of changing
the SDK input buffer or speaking/closing automatically. The window close button
also produces code 53 with empty text, allowing the host to save or refuse to
close. The host owns document state, shortcuts and the decision to leave its
loop. F2 remains SDK-controlled. `allow_capture(false)` disables its capture
toggle while, for example, a speech worker prepares; it does not stop an already
active capture or restrict direct calls to `Capture.start()`.

`macos.window_events.CloseRequests.create(a, window)` implements close-button
interception underneath `App`. Its delegate sets a stable flag and refuses
native closure; `take()` consumes the flag. `close()` detaches and releases the
delegate and is repeatable. Keep its allocator and window alive through close,
use it only on the main thread, and do not copy a live owning handle. `App`
manages this lifecycle automatically when editable mode is enabled. This is
window-close interception, not application-termination or unsaved-document UI.

## Atomic file publication

`macos.file.replace(a, path, bytes, existing)` returns
`Res<(), FileError | AllocError>`. Pass a short-lived scratch arena: temporary
memory belongs to that allocator until its arena is destroyed. Native file
descriptors and staging paths are cleaned up before return. The parent directory
must exist. Empty paths, embedded NULs, and final-component symlinks are refused.

The helper writes a same-directory temporary file, fsyncs and closes it, then
publishes it. With `existing: false`, exclusive hardlink publication refuses any
existing destination, including one created after the caller checked. New files
start with private 0600 permissions. With `existing: true`, it copies permissions,
ACLs and extended attributes, refreshes access/modification time, and atomically
renames over the destination. It uses direct Darwin bindings; no C shim is needed.

Applications must detect external edits themselves. Existing-file rename still
has a check-to-publication race with concurrent writers; this is not
compare-and-swap. Parent-directory symlinks are allowed. No directory fsync is
performed, so power-loss durability is not promised. This is a blocking API;
large writes and syncs belong outside a latency-sensitive UI loop.

```sh
python3 tests/file/run.py
```

The headless native test covers new/existing saves, executable permissions,
extended attributes, fresh modification time, empty content, collisions, missing
paths, symlink refusal and staging cleanup. It does not inject disk-full or fsync
failures. See [test details](tests/file/README.md).

## Architecture

- `src/native.zen`: header-backed native declarations and explicit typed
  Objective-C message signatures.
- `src/objc.zen`: Zen helpers for selectors, classes, native strings, and
  Objective-C ownership.
- `src/macos.zen`: window lifecycle, input, rendering, and speech in Zen.
- `src/window_events.zen`: main-thread close interception for app-owned editing.
- `src/file.zen`: atomic file publication and macOS metadata preservation.
- `src/pacing.zen`: main-run-loop Metal display-link delegate and older-system
  deadline fallback; direct native bindings with Zen callback state.
- `src/display.zen`: submitted-frame timing using portable `std.stats` samples.
- `src/mlx.zen`: optional declarations for MLX C's Metal availability/capture
  APIs. This is not an inference engine and is not linked into the console.
- `build.zen`: native library dependency, Objective-C compilation language,
  and explicit Apple frameworks. No source paths smuggled into linker flags.

The initial renderer clears a Metal drawable and composites a CATextLayer.
Glyph rasterization is supplied by Core Animation. A custom Metal glyph atlas,
terminal emulation/PTY, selection, paste, and IME are not implemented yet.

The caller supplies the input allocator. Input storage is allocated once with
4096 bytes of capacity; appends cannot grow it. Each event/frame has a fresh
Zen arena and a native autorelease pool, both released at the iteration's end.
The window, Metal queue/device, and speech synthesizer have explicit native
ownership. No claim about allocator or actor speed is made without measurement.
AppKit and rendering stay on the main thread. A future inference worker can own
its MLX state in an actor and send results back; native UI handles must not be
passed into background actors.

## Binding syntax

```zen
Libc = c.bind("unistd.h", {
    close* = (fd: c_int) c_int
})
```

A binding namespace contains non-generic function signatures. The C header
supplies declarations; calls emit the native function name directly. Export a
namespace with `*` to import it from another Zen module.

For APIs with an explicitly selected calling signature, a native symbol can
be supplied separately:

```zen
Message = c.bind("objc/message.h", "objc_msgSend", {
    object* = (receiver: Ptr<()>, selector: Ptr<()>) Ptr<()>
})
```

This emits a typed function-pointer call to the existing native symbol, not a
wrapper function. The author is responsible for matching the method ABI.
The CGRect return signature currently assumes Apple silicon; Intel's separate
struct-return message entry point is not implemented here.

This first binding form does not translate whole C headers, import C record
layouts/constants automatically, or accept an inline binding as `b.lib`'s
argument. Bindings live in ordinary `.zen` modules; the existing `b.lib` graph
records their native link dependencies.

## MLX

`src/mlx.zen` matches the public [MLX C Metal API](https://github.com/ml-explore/mlx-c/blob/main/mlx/c/metal.h).
Using it requires installing/building MLX C and supplying its include and
library paths to an MLX-enabled target. MLX C is not installed or vendored by
this project, and no MLX execution is claimed by the console smoke test.
The rendering window uses Metal independently of MLX.

## Ownership regression

```sh
ZEN_STD=../zen/src ../zen/zen build tests/ownership
./build/ownership
```

This desktop-only test sweeps 128 allocator budgets through window creation
and closes every successful app twice. It checks allocation error paths and
repeatable cleanup; it is not a native heap leak profiler. The test and smoke
run must execute on the main thread with WindowServer access.

## Microphone capture and app-owned processing

`macos.audio.Capture` owns a main-run-loop AudioQueue. `create(a)` allocates
bounded buffers but does not start recording. `start()` is an explicit user
action; `stop()` disposes the queue. Call `poll()` during event processing to
stop on callback failure or the default bounded 30-second limit. `samples(out)`
copies the latest 1024 mono samples; `recording()` borrows up to 30 seconds of
16 kHz float32 audio until the next recording or prefix discard. Keep the allocator
alive through `stop()`. Callback access to arena state is detached before native
shutdown, so releasing that arena afterward is safe even if disposal fails.
`closed()` confirms native queue disposal. A failed disposal retains an inert,
pointer-sized native callback token and the native queue; retry `stop()` while
the Capture arena remains alive to reclaim them. Restart is refused until cleanup
succeeds. Permanent failures intentionally quarantine those native resources until
process exit. `CAPTURE_ALLOCATION_FAILED` (`-70002`) reports token allocation failure.
Callbacks and all Capture operations must run on the creating main CFRunLoop;
this is serialized ownership, not atomic cross-thread access. A live Capture must
not be copied.

`python3 tests/audio/run_disposal.py` tests native failure paths without accessing
the microphone. `--negative-control` confirms missing callback detachment fails.

The app bundle declares `NSMicrophoneUsageDescription`. macOS controls access;
first recording attempts can prompt, and a denial must be changed in System
Settings > Privacy & Security > Microphone. `permission(a)` queries authorization
without prompting and `permission_text` explains its state. AudioQueue success
alone does not prove authorized, non-silent input.

The demo uses F2 to toggle recording, shows permission/error status and measured
Metal submission FPS. `App.begin(a)` and `App.tick(a)` let a host application own
the loop, perform its own work, and call `App.spectrum(levels)` with 32 normalized
bar heights or `App.set_input(a,text)` with a transcript. CATextLayer and CALayer
present text/bars; FPS measures submitted frames, not GPU completion.

FFT/WAV processing belongs to the separate `zen-audio` library. Local model
inference belongs to `zen-parakeet`; neither is a dependency of this SDK.
`zen-tui` composes them. Capture callbacks do no allocation and execute on the
same main CFRunLoop as snapshot reads.

For live transcription, `recording()` also works while capture is active: each
call returns the current bounded prefix and sample count. Copy or serialize
that prefix on the main thread before giving it to a worker; do not share the
borrowed sample pointer with a background actor. `session()` starts at zero
and changes whenever a new start attempt clears the recording, including a
failed attempt. Tag worker requests and replies with it to discard replies
from earlier captures. `generation()` still advances on stop and can trigger
a final transcription. Repeated `start()` while active keeps the same session;
repeated `stop()` keeps both counters unchanged.

Zen actors currently use one pthread per actor with a bounded 64-message
mailbox, mutex, and condition variable. They do not run on AppKit's main run
loop or automatically marshal work back to it. AudioQueue callbacks are
explicitly scheduled on the main CFRunLoop; native UI updates and capture
views stay there. A worker should return copied data/results for the UI to
consume on a later frame.

Use `env.clock.since_start()` for application elapsed time and smoothing.
`macos.display.monotonic()` returns Core Animation monotonic seconds for native
display timing; do not mix timestamp domains. `Config.spectrum_label` defaults to `"FFT"`; applications can supply a
label describing their displayed frequency range. Like the other config text,
this string is borrowed and must remain valid throughout the app's run loop.

The status display keeps authorization and observed capture separate.
`Capture.received_audio()` records whether the current capture session has
delivered nonzero samples; it resets on a new start attempt. When the native
authorization query is undetermined or unavailable but audio has arrived,
`capture_permission_text` reports “Microphone audio received” instead of claiming
a permission prompt is pending. Explicit denied/restricted results remain
visible. This does not reinterpret the native result as an authorization grant.

### Continuous capture

The SDK defaults to a bounded 30-second recording. Before starting, an app can
call `capture.continuous(true)` to opt into consumption of an ongoing stream.
It returns false if a queue is already open. After copying/submitting an audio
segment to its worker, the main-thread app calls `discard_prefix(sample_count)`.
This shifts the remaining prefix safely, without changing the FFT ring, signal
state, capture session, or stop generation. Existing borrowed recording views
are invalidated by the discard. Invalid counts return false without mutation.

The buffer still holds at most 480000 samples. If a continuous consumer falls
behind, `CAPTURE_OVERFLOW` (`-70001`) is reported and `poll()` stops capture;
there is no silent overwrite or unreported audio loss. A new start clears that
error. Capture views include samples already delivered by AudioQueue callbacks;
an immediate stop can discard samples still pending in the hardware queue.

Run the synthetic callback-state checks without opening a microphone:

```sh
python3 tests/audio/run_continuous.py --zen ../zen/zen
```

They exercise overlapping/empty/full/invalid prefix removal, unchanged FFT and
session state, more than 30 seconds with periodic consumption, sticky overflow,
and the unchanged bounded default.

`Config.input_tail_bytes` controls how much recent input is displayed. Its
zero default displays all text. A positive limit shows the last bytes, advances
the boundary to a UTF-8 codepoint, and prefixes an ellipsis when text is omitted;
the full input buffer remains available. Zen Code uses 600 bytes to keep recent
dictation visible in the default 960×600 window. Smaller windows can still clip
text; this is a display limit, not scrolling or text truncation in storage.

### Bundle resources

`resource_directory(a)` from `macos.bundle` returns an optional owned String
with the main bundle's resource directory. It copies Foundation's UTF-8 path
before draining its local autorelease pool, and works from the bundled
executable regardless of the shell working directory. Applications own the
configuration format and filesystem policy; this helper does not load a model
or write settings. Writable application settings belong outside a signed app bundle.

Reproducible capture-buffer measurements are in [benchmarks](benchmarks/README.md)
and [measured results](benchmarks/RESULTS.md); they do not activate a microphone.

## Display pacing and threading

On macOS 14+, `CAMetalDisplayLink` supplies a drawable on the main run loop.
`App.tick` pumps that loop and submits only when a display update is ready;
audio and other native sources may wake a tick without rendering. Do not count
ticks as frames. The link requests 60 Hz; the system controls actual scheduling.
On macOS 13 or when the native link is unavailable, an absolute 60 Hz deadline
fallback avoids adding a fixed sleep to each frame's work.

The delegate callback retains the latest drawable in stable allocator-owned
state. It never receives an `App` address, calls user code, allocates Zen memory,
or dispatches an actor. Close invalidates the link before releasing its delegate
and pending drawable, before the caller may free the allocator. Lifecycle calls,
`tick`, capture reads and all native UI operations must stay on the main thread.
Inference belongs to a separate library's worker actor and returns copied data.

The voice overlay displays host-supplied three-second mean/min/max pitch and
simple deep/mid/high bands; pitch detection belongs to `zen-audio`, not the
native SDK. The display timing tracker retains rolling 1/3-second submission
rates and p95/p99 submission intervals. These measure neither GPU durations
nor actual presentation. The native `tests/display` executable checks steady
rates, wraparound, rate changes and stalls with deterministic timestamps.
`display_link()`, `display_updates()` and
`coalesced_updates()` expose scheduler diagnostics. A coalesced update means a
new callback replaced a drawable not yet consumed by a tick, not a measured
missed presentation deadline. No per-frame network telemetry is emitted.

Run the display and hidden-window close-delegate regressions through Zen's
native executable test runner (from this repository):

```sh
ZEN_STD=../zen/src CFLAGS='-O2 -Wno-parentheses-equality' ../zen/zen test tests/display
ZEN_STD=../zen/src CFLAGS='-O2 -Wno-parentheses-equality' ../zen/zen test tests/window_events
```

Both executables enforce a 15-second runtime deadline with the macOS `alarm`
API. Build artifacts stay under ignored `build/`; CI should separately enforce
a build timeout (the former Python wrappers used 120 seconds).

Desktop regression (three 120-frame link lifecycles, repeated closes, and
link-free deadline fallback):

```sh
ZEN_STD=../zen/src ../zen/zen build tests/pacing
./build/pacing
./build/pacing --steady
```

The `--steady` variant runs one 360-frame window, leaving startup outside the
last 240 intervals. Each test window has a fifteen-second bound per window. An occluded or minimized window can
be throttled by macOS; run this test in a visible desktop session. The SDK smoke
requires 30 submitted frames within 30 seconds.

Construction cleans up its current native handles on allocation failure. The
ownership regression checks allocation failures and repeated closes; it is not
a native heap leak audit. See [desktop validation](docs/PERFORMANCE.md) for
measured lifecycle, pacing and trace results, including unresolved limitations.

## Camera and voice-processing APIs

Initial `macos.camera` and `macos.voice_processing` APIs expose camera discovery,
a permission-gated preview session, microphone-mode queries and stopped-engine
voice-processing configuration. See [native media status](docs/MEDIA.md) for
ownership rules, test results and the remaining live-capture integration work.
