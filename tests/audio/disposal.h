// Fault-injection ABI fixture only; production callbacks and lifetime policy are Zen.
#include <AudioToolbox/AudioToolbox.h>
#include <stdlib.h>
static int dispose_fail, allocation_fail, creation_fail, token_count, create_count;
static void *last_user;
static void test_config(int disposal, int allocation, int creation) {
    dispose_fail = disposal; allocation_fail = allocation; creation_fail = creation;
}
static int test_tokens(void) { return token_count; }
static int test_creates(void) { return create_count; }
static void *test_user(void) { return last_user; }
static void *test_malloc(size_t n) {
    if (allocation_fail) return NULL;
    void *p = malloc(n); if (p) token_count++; return p;
}
static void test_free(void *p) { if (p) token_count--; free(p); }
static OSStatus TestAudioQueueNewInput(const AudioStreamBasicDescription *f,
 AudioQueueInputCallback cb, void *user, CFRunLoopRef loop, CFStringRef mode,
 UInt32 flags, AudioQueueRef *out) {
    create_count++; last_user = user;
    if (creation_fail) return -90002;
    *out = (AudioQueueRef)0x1234; return 0;
}
static OSStatus TestAudioQueueAllocateBuffer(AudioQueueRef q, UInt32 n, AudioQueueBufferRef *b) {
    *b = (AudioQueueBufferRef)0x5678; return 0;
}
static OSStatus TestAudioQueueEnqueueBuffer(AudioQueueRef q, AudioQueueBufferRef b, UInt32 n, const AudioStreamPacketDescription *d) { return 0; }
static OSStatus TestAudioQueueStart(AudioQueueRef q, const AudioTimeStamp *t) { return 0; }
static OSStatus TestAudioQueueStop(AudioQueueRef q, Boolean b) { return 0; }
static OSStatus TestAudioQueueDispose(AudioQueueRef q, Boolean b) { return dispose_fail ? -90001 : 0; }
