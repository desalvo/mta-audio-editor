// Stable DSP-only C ABI. No device IO, plug-in loading, allocation or locking.
#pragma once
#include <stddef.h>
#if defined(_WIN32)
# if defined(MTA_AUDIO_CORE_EXPORTS)
#  define MTA_DSP_API __declspec(dllexport)
# else
#  define MTA_DSP_API __declspec(dllimport)
# endif
#else
# define MTA_DSP_API __attribute__((visibility("default")))
#endif
#ifdef __cplusplus
extern "C" {
# define MTA_DSP_NOEXCEPT noexcept
#else
# define MTA_DSP_NOEXCEPT
#endif
MTA_DSP_API unsigned mta_render_dsp_abi(void) MTA_DSP_NOEXCEPT;
// 1..4096 frames, 1..64 interleaved channels, finite gain 0..128.
// Invalid data leaves every output sample unchanged; no clipping is applied.
MTA_DSP_API int mta_render_gain(float* pcm,size_t frames,unsigned channels,float gain) MTA_DSP_NOEXCEPT;
// Stereo inputs already converted at the negotiated sample rate. Linear balance
// matches the current exporter: center preserves L/R, extremes silence one side.
// 1..64 routes; muted inputs may be null. No buffers may overlap output.
MTA_DSP_API int mta_render_mix(const float* const* inputs,const float* gains,
    const float* pans,const unsigned char* enabled,size_t routes,float* output,size_t frames) MTA_DSP_NOEXCEPT;
// Absolute frame offsets make fade results independent of processing block size.
// total_frames is the prepared project's pre-time-stretch duration.
MTA_DSP_API int mta_render_envelope(float* pcm,size_t frames,unsigned channels,
    unsigned long long offset,unsigned long long total_frames,float gain,
    unsigned long long fade_in,unsigned long long fade_out) MTA_DSP_NOEXCEPT;
#ifdef __cplusplus
}
#endif
