#pragma once
// RT-safe finite PCM sanitiser for native VST3/output buffers (no allocations).
#include <cmath>
#include <cstddef>

namespace mta {
inline bool sanitize_audio_block(float* data, std::size_t samples, float limit = 1.0f) noexcept {
    if ((!data && samples) || !std::isfinite(limit) || limit <= 0.0f || limit > 1.0f) return false;
    for (std::size_t i = 0; i < samples; ++i) {
        float v = data[i];
        if (!std::isfinite(v)) v = 0.0f;
        data[i] = v > limit ? limit : (v < -limit ? -limit : v);
    }
    return true;
}
} // namespace mta
