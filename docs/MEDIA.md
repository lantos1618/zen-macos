# Native camera and voice processing

## Library boundaries

`zen-audio` remains portable audio analysis/buffer/DSP code. Apple camera and
voice-processing APIs live in `zen-macos`; a corresponding iOS adapter belongs
in `zen-ios`. Neither is currently wired into the shared Zen UI playground.
The Zen Call experimental target in zen-tui now uses the macOS camera API.
Introduce `zen-video` when portable frame/pixel operations are implemented, and
`zen-media` when there is working synchronized playback/container logic. No empty
packages are introduced by this change.

## Camera

`macos.camera.permission(a)` queries AVFoundation authorization without prompting.
`available(a)` detects a default video device without starting a capture session.
An available device does not imply authorization or successful streaming.

`PreviewSession.create(a)` requires existing camera authorization, creates an
AVCaptureSession with a camera-only input, and owns an AVCaptureVideoPreviewLayer.
`layer()` borrows the layer. `start()` checks whether the session starts;
`active()` reports isRunning. `close()` stops and releases native ownership and
is idempotent across copies sharing the allocator-backed handle storage.

Serialize lifecycle operations and keep the allocator alive through close.
Provide an autorelease pool on that thread. start/stop are blocking native APIs;
use a dedicated session owner rather than starting capture in a UI frame callback.
Attach/detach the preview layer on the UI thread, and detach before closing the
session. No simultaneous lifecycle operations are supported.

`PreviewSession.request(a)` is the explicit user-action alternative: it permits
NotDetermined authorization and uses Apple's documented automatic permission
prompt on AVCaptureDeviceInput creation. Poll authorization before starting.
Denied/restricted access is rejected. The bundle needs NSCameraUsageDescription.
`create(a)` retains its strict already-authorized behavior.

This is an initial native API, not a finished CameraView. Zen Call now supplies
the bundle description, worker lifecycle and UI attachment; live preview was
visually verified there. There
is no frame callback, recording, encoding, video actor pipeline or audio input.
Runtime device removal/error notification handling is also pending.

## Voice processing

`macos.voice_processing.microphone_modes(a)` reports the user's preferred and
currently active AVFoundation microphone modes. Unsupported selectors produce
Unavailable. Modes are Standard, WideSpectrum and VoiceIsolation; future unknown
values also map to Unavailable. Preferred and active may differ by audio route.
These are queries, not proof that our current AudioQueue capture is processed.

`set_enabled(a, engine, enabled)` configures Apple's voice processing on a valid,
caller-owned AVAudioEngine. It rejects null engines, running engines, unsupported
nodes and native refusal. Serialize access with the engine owner. Configuration
applies to device rendering; manual rendering is unsupported by Apple.

The existing `macos.audio.Capture` uses AudioQueue and is unchanged. Enabling this
API on a different engine does not process that queue. A future engine capture
backend must route playback/capture correctly, copy into bounded buffers without
allocation or actor sends in real-time callbacks, and hand off to a worker.
The actor runtime and native callback lifetime must not be conflated.

Echo cancellation removes playback leaking into the microphone. Background-noise
suppression attenuates unwanted environmental sounds. Voice Isolation is a
user-selected microphone mode, distinct from enabling engine voice processing.
No claim is made about WhatsApp's internals or matching FaceTime quality.

Apple references:
- https://developer.apple.com/videos/play/wwdc2019/510/
- https://developer.apple.com/videos/play/wwdc2021/10047/
- SDK AVAudioIONode.h: setVoiceProcessingEnabled:error: requires a stopped engine
  and switches both input/output nodes; device rendering only.
- SDK AVCaptureDevice.h: microphone mode properties are read-only.

## Verification

From zen-macos:

```sh
ZEN_STD=../zen/src ../zen/build/dev/actor-zen build tests/media
build/media-probe
```

The default probe never starts capture. On this Mac (2026-09-27), it found a
camera, reported authorization NotDetermined, and exposed both microphone-mode
queries. Invalid engine and unauthorized session guards pass. Native API source
compiles through the existing Zen compiler with header-backed c.bind calls;
no C/Objective-C implementation strings or compiler changes were added.

`build/media-probe --camera-lifecycle` is an opt-in start/close check requiring
an already authorized identity. It has NOT been run here. No live preview,
processed audio stream, cancellation quality or sustained memory soak has been
verified by this probe. Zen Call subsequently verified a live camera preview
and unprocessed microphone-to-actor audio delivery; see zen-tui/docs/CALL.md.
Native errors currently report categories rather than NSError details.
