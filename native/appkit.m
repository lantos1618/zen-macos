#import <AppKit/AppKit.h>

#include <stdint.h>
#include <stdlib.h>

typedef struct {
    NSApplication *application;
    NSMutableArray<NSWindow *> *windows;
} ZenMacApp;

void *zen_macos_app_create(const char *name) {
    @autoreleasepool {
        ZenMacApp *app = calloc(1, sizeof(*app));
        if (app == NULL) return NULL;

        app->application = [NSApplication sharedApplication];
        app->windows = [[NSMutableArray alloc] init];
        [app->application setActivationPolicy:NSApplicationActivationPolicyRegular];

        NSString *title = [NSString stringWithUTF8String:name ?: "Zen App"];
        [[NSProcessInfo processInfo] setProcessName:title];
        return app;
    }
}

void *zen_macos_window_create(void *raw_app, const char *title, int64_t width, int64_t height) {
    @autoreleasepool {
        ZenMacApp *app = raw_app;
        if (app == NULL) return NULL;

        NSRect frame = NSMakeRect(0, 0, (CGFloat)width, (CGFloat)height);
        NSWindowStyleMask style = NSWindowStyleMaskTitled |
                                  NSWindowStyleMaskClosable |
                                  NSWindowStyleMaskMiniaturizable |
                                  NSWindowStyleMaskResizable;
        NSWindow *window = [[NSWindow alloc] initWithContentRect:frame
                                                       styleMask:style
                                                         backing:NSBackingStoreBuffered
                                                           defer:NO];
        if (window == nil) return NULL;
        [window setTitle:[NSString stringWithUTF8String:title ?: "Window"]];
        [window center];
        [app->windows addObject:window];
        return (__bridge void *)window;
    }
}

void zen_macos_window_show(void *raw_window) {
    @autoreleasepool {
        NSWindow *window = (__bridge NSWindow *)raw_window;
        [window makeKeyAndOrderFront:nil];
    }
}

int32_t zen_macos_app_run(void *raw_app) {
    @autoreleasepool {
        ZenMacApp *app = raw_app;
        if (app == NULL) return 1;
        [app->application activateIgnoringOtherApps:YES];
        [app->application run];
        return 0;
    }
}

void zen_macos_app_destroy(void *raw_app) {
    @autoreleasepool {
        ZenMacApp *app = raw_app;
        if (app == NULL) return;
        [app->windows removeAllObjects];
        app->windows = nil;
        free(app);
    }
}

