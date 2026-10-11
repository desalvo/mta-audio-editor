#pragma once
#include <cmath>
#include <cstddef>

namespace mta::audio {
// Lightweight hard noise gate, non-allocating callback-safe processing.
inline bool noise_gate(float* samples, std::size_t sample_count, float threshold) noexcept {
    if (!samples || !std::isfinite(threshold) || threshold < 0.0f || threshold > 1.0f) return false;
    for (std::size_t i = 0; i < sample_count; ++i) {
        const float value = samples[i];
        samples[i] = !std::isfinite(value) || std::fabs(value) < threshold ? 0.0f : value;
    }
    return true;
}
} // namespace mta::audio
