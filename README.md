# Zen macOS

A native Apple-silicon macOS app written in current Zen. It opens a resizable,
Retina-aware Metal window, keeps a bounded UTF-8 input buffer in Zen, and speaks
entered text using AVFoundation. There is no handwritten C or Objective-C
implementation: `native/appkit.m` has been removed.

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

`zen-tui` is a separate application that depends on this SDK. Its app entry
contains its own copy and configuration, while window, input, GPU presentation,
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

## Architecture

- `src/native.zen`: header-backed native declarations and explicit typed
  Objective-C message signatures.
- `src/objc.zen`: Zen helpers for selectors, classes, native strings, and
  Objective-C ownership.
- `src/macos.zen`: window lifecycle, input, rendering, and speech in Zen.
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
stop on callback failure or after the 30-second recording limit. `samples(out)`
copies the latest 1024 mono samples; `recording()` borrows up to 30 seconds of
16 kHz float32 audio until the next recording. Keep the allocator alive until
`closed()` confirms queue disposal. A live Capture must not be copied.

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

Validation: actual F2 microphone start/FFT activity/stop passed in the app;
fresh-denial permission UI was not exercised. Updated allocation sweep passed
215 failure cases and 297 successful repeated closes. This is not a native heap
leak audit; CoreAnalytics emitted two context-leak diagnostics during the sweep.

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

`macos.display.monotonic()` returns Core Animation monotonic seconds. Use
elapsed differences to drive smoothing so animation does not depend on frame
rate. `Config.spectrum_label` defaults to `"FFT"`; applications can supply a
label describing their displayed frequency range. Like the other config text,
this string is borrowed and must remain valid throughout the app's run loop.

The status display keeps authorization and observed capture separate.
`Capture.received_audio()` records whether the current capture session has
delivered nonzero samples; it resets on a new start attempt. When the native
authorization query is undetermined or unavailable but audio has arrived,
`capture_permission_text` reports “Microphone audio received” instead of claiming
a permission prompt is pending. Explicit denied/restricted results remain
visible. This does not reinterpret the native result as an authorization grant.
