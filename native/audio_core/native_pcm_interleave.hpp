// PCM planar/interleaved conversion for offline and realtime native bridges.
// Caller-owned buffers; no dynamic allocations and no throws.
#pragma once
#include <cmath>
#include <cstddef>
namespace mta::audio {
inline bool interleave_pcm(const float* const* planar, float* out,
                           std::size_t frames, std::size_t channels) noexcept {
    if (!planar || !out || !frames || frames > 8192 || !channels || channels > 8) return false;
    for (std::size_t c = 0; c < channels; ++c) {
        if (!planar[c]) return false;
        for (std::size_t f = 0; f < frames; ++f)
            if (!std::isfinite(planar[c][f])) return false;
    }
    for (std::size_t f = 0; f < frames; ++f)
        for (std::size_t c = 0; c < channels; ++c)
            out[f * channels + c] = planar[c][f];
    return true;
}
inline bool deinterleave_pcm(const float* input, float* const* planar,
                             std::size_t frames, std::size_t channels) noexcept {
    if (!planar || !input || !frames || frames > 8192 || !channels || channels > 8) return false;
    for (std::size_t c = 0; c < channels; ++c) if (!planar[c]) return false;
    for (std::size_t i = 0; i < frames * channels; ++i)
        if (!std::isfinite(input[i])) return false;
    for (std::size_t f = 0; f < frames; ++f)
        for (std::size_t c = 0; c < channels; ++c)
            planar[c][f] = input[f * channels + c];
    return true;
}
} // namespace mta::audio
