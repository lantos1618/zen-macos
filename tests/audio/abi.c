// Verify the explicit Zen layouts against this machine's Apple SDK.
#include <AudioToolbox/AudioToolbox.h>
#include <stddef.h>
#include <stdint.h>
struct ZenFormat {
    double rate;
    uint32_t format, flags, bytes_per_packet, frames_per_packet;
    uint32_t bytes_per_frame, channels, bits, reserved;
};
struct ZenBufferPrefix { uint32_t capacity; float *data; uint32_t size; };
#define FIELD(zen, a, apple, b) _Static_assert(offsetof(zen, a) == offsetof(apple, b), #a " ABI")
_Static_assert(sizeof(struct ZenFormat) == sizeof(AudioStreamBasicDescription), "ASBD size");
FIELD(struct ZenFormat, rate, AudioStreamBasicDescription, mSampleRate);
FIELD(struct ZenFormat, format, AudioStreamBasicDescription, mFormatID);
FIELD(struct ZenFormat, flags, AudioStreamBasicDescription, mFormatFlags);
FIELD(struct ZenFormat, bytes_per_packet, AudioStreamBasicDescription, mBytesPerPacket);
FIELD(struct ZenFormat, frames_per_packet, AudioStreamBasicDescription, mFramesPerPacket);
FIELD(struct ZenFormat, bytes_per_frame, AudioStreamBasicDescription, mBytesPerFrame);
FIELD(struct ZenFormat, channels, AudioStreamBasicDescription, mChannelsPerFrame);
FIELD(struct ZenFormat, bits, AudioStreamBasicDescription, mBitsPerChannel);
FIELD(struct ZenFormat, reserved, AudioStreamBasicDescription, mReserved);
FIELD(struct ZenBufferPrefix, capacity, AudioQueueBuffer, mAudioDataBytesCapacity);
FIELD(struct ZenBufferPrefix, data, AudioQueueBuffer, mAudioData);
FIELD(struct ZenBufferPrefix, size, AudioQueueBuffer, mAudioDataByteSize);
_Static_assert(sizeof(struct ZenBufferPrefix) <= sizeof(AudioQueueBuffer), "prefix within buffer");
_Static_assert(kAudioFormatLinearPCM == 1819304813, "PCM format");
_Static_assert((kAudioFormatFlagIsFloat | kAudioFormatFlagIsPacked) == 9, "float flags");
int main(void) { return 0; }
