#pragma once
#include <cmath>
#include <cstddef>
#include <limits>
namespace mta::audio {
// Stateless soft-clipper for interleaved float PCM. Not a loudness normalizer.
inline bool soft_clip(float* pcm, std::size_t frames, std::size_t channels,
                      float drive = 1.0f) noexcept {
    if (!pcm || frames == 0 || channels == 0 || channels > 64 ||
        frames > std::numeric_limits<std::size_t>::max()/channels ||
        !std::isfinite(drive) || drive <= 0.0f || drive > 16.0f) return false;
    const auto samples = frames * channels;
    for (std::size_t i = 0; i < samples; ++i) {
        const float v = pcm[i];
        pcm[i] = std::isfinite(v) ? std::tanh(v * drive) : 0.0f;
    }
    return true;
}
}  // namespace mta::audio
