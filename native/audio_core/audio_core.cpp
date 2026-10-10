#include <cmath>
#include <cstddef>
#include <cstdint>
#if defined(_WIN32)
# define MTA_EXPORT extern "C" __declspec(dllexport)
#else
# define MTA_EXPORT extern "C" __attribute__((visibility("default")))
#endif
// Contiguous interleaved float32 PCM. No allocation, no exceptions, no plugin loading.
// The caller controls threading; this function is safe from the realtime audio thread.
MTA_EXPORT int mta_pcm_meter(const float* pcm, std::size_t frames, unsigned channels,
                             float* peak_out, float* rms_out) noexcept {
  if (!pcm || !peak_out || !rms_out || channels < 1 || channels > 64 ||
      frames == 0 || frames > SIZE_MAX / channels) return -1;
  const auto count = frames * channels;
  double sum = 0.0;
  float peak = 0.0f;
  for (std::size_t n = 0; n < count; ++n) {
    const float v = pcm[n];
    if (!std::isfinite(v)) return -2;
    const float a = std::fabs(v);
    if (a > peak) peak = a;
    sum += static_cast<double>(v) * static_cast<double>(v);
  }
  *peak_out = peak;
  *rms_out = static_cast<float>(std::sqrt(sum / static_cast<double>(count)));
  return 0;
}
MTA_EXPORT unsigned mta_audio_core_abi() noexcept { return 1; }

// In-place PCM gain for optional accelerated DSP. No allocation or locking.
// Reject nonfinite data before writing to avoid partially modified buffers.
MTA_EXPORT int mta_pcm_gain(float* pcm, std::size_t frames, unsigned channels, float gain) noexcept {
  if (!pcm || channels < 1 || channels > 64 || frames == 0 ||
      frames > SIZE_MAX / channels || !std::isfinite(gain) || gain < 0.0f || gain > 128.0f) return -1;
  const auto count = frames * channels;
  for (std::size_t i=0; i<count; ++i)
    if (!std::isfinite(pcm[i]) || !std::isfinite(pcm[i] * gain)) return -2;
  for (std::size_t i=0; i<count; ++i) pcm[i] *= gain;
  return 0;
}

// Sum one interleaved PCM buffer into an existing destination buffer.
// A primitive for a future realtime mixer/host: no allocation, locks or I/O.
// Validation is completed before any output is modified. The caller must ensure
// source and destination do not overlap, and serialize writes to destination.
MTA_EXPORT int mta_pcm_accumulate(float* destination, const float* source,
                                  std::size_t frames, unsigned channels,
                                  float gain) noexcept {
  if (!destination || !source || destination == source || channels < 1 || channels > 64 ||
      frames == 0 || frames > SIZE_MAX / channels || !std::isfinite(gain) ||
      gain < -128.0f || gain > 128.0f) return -1;
  const auto count = frames * channels;
  for (std::size_t i=0; i<count; ++i) {
    const float mixed = destination[i] + source[i] * gain;
    if (!std::isfinite(destination[i]) || !std::isfinite(source[i]) ||
        !std::isfinite(mixed)) return -2;
  }
  for (std::size_t i=0; i<count; ++i) destination[i] += source[i] * gain;
  return 0;
}

// Convert interleaved float PCM into per-channel planar float buffers used by
// VST3 ProcessData, without allocating. Supports 1..64 channels. Input/output
// pointers may not alias; all outputs are validated before writing.
MTA_EXPORT int mta_pcm_deinterleave(const float* source, float* const* channels_out,
                                    std::size_t frames, unsigned channels) noexcept {
  if (!source || !channels_out || channels == 0 || channels > 64 || frames == 0 ||
      frames > SIZE_MAX / channels) return -1;
  for (unsigned c=0;c<channels;++c) {
    if (!channels_out[c]) return -1;
    for (unsigned earlier=0;earlier<c;++earlier)
      if (channels_out[c] == channels_out[earlier]) return -1;
  }
  for (std::size_t n=0;n<frames*channels;++n) if (!std::isfinite(source[n])) return -2;
  for (std::size_t frame=0;frame<frames;++frame)
    for (unsigned c=0;c<channels;++c) channels_out[c][frame] = source[frame*channels+c];
  return 0;
}
MTA_EXPORT int mta_pcm_interleave(const float* const* channels_in, float* dest,
                                  std::size_t frames, unsigned channels) noexcept {
  if (!dest || !channels_in || channels == 0 || channels > 64 || frames == 0 ||
      frames > SIZE_MAX / channels) return -1;
  for (unsigned c=0;c<channels;++c) if (!channels_in[c]) return -1;
  for (unsigned c=0;c<channels;++c)
    for (std::size_t i=0;i<frames;++i)
      if (!std::isfinite(channels_in[c][i])) return -2;
  for (std::size_t frame=0;frame<frames;++frame)
    for (unsigned c=0;c<channels;++c) dest[frame*channels+c] = channels_in[c][frame];
  return 0;
}

// Stereo constant-power pan mixer for a mono source. The gain coefficient is
// applied before panning; center (-3 dB per side) maintains perceived loudness.
// Validation is transactional: bad input never modifies the destination.
// pan = -1 left, 0 center, +1 right. Frames are interleaved LRLR...
MTA_EXPORT int mta_pcm_mix_mono_stereo(float* stereo_destination,
                                       const float* mono_source,
                                       std::size_t frames,
                                       float gain, float pan) noexcept {
  if (!stereo_destination || !mono_source || frames == 0 ||
      frames > SIZE_MAX / 2 || !std::isfinite(gain) ||
      !std::isfinite(pan) || gain < -128.0f || gain > 128.0f ||
      pan < -1.0f || pan > 1.0f) return -1;
  constexpr float kPiOverFour = 0.7853981633974483096f;
  const float angle = (pan + 1.0f) * kPiOverFour;
  const float l = gain * std::cos(angle);
  const float r = gain * std::sin(angle);
  for (std::size_t i = 0; i < frames; ++i) {
    const float sample = mono_source[i];
    const float dl = stereo_destination[i * 2];
    const float dr = stereo_destination[i * 2 + 1];
    if (!std::isfinite(sample) || !std::isfinite(dl) || !std::isfinite(dr) ||
        !std::isfinite(dl + sample * l) ||
        !std::isfinite(dr + sample * r)) return -2;
  }
  for (std::size_t i = 0; i < frames; ++i) {
    stereo_destination[i * 2] += mono_source[i] * l;
    stereo_destination[i * 2 + 1] += mono_source[i] * r;
  }
  return 0;
}
