# zen-macos

An experimental, allocator-explicit AppKit wrapper for Zen.

The public lifetime is direct: initialize an app with an allocator, create
app-owned windows, run it, then deinitialize it. Objective-C objects remain in
the native ownership domain; owned Zen values use the allocator stored by
`MacApp<A>`.

```zen
heap := sys.heap()
app := mac_app_init(heap.addr(), "My App").expect("start AppKit")
window := app.window("Hello", 800, 500).expect("create window")
window.show()
code := app.run()
app.deinit()
```

## Build on macOS

Install Xcode command-line tools and make `zenc` available at `../zenc`, then:

```sh
../zenc build .
./hello-mac
```

The build uses Zen's first-class native-source, framework, library, and host-OS
configuration:

```zen
exe("hello-mac")
    .sources(["native/appkit.m"])
    .frameworks(["AppKit", "Foundation"])
    .libraries(["objc"])
```
