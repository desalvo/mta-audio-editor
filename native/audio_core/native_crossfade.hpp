#pragma once
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <limits>

namespace mta::audio {
// Crossfade between original and rendered preview. Prevalidated and allocation-free.
class NativeCrossfade {
public:
    bool process(const float* original, const float* processed, float* output,
                 std::size_t frames, std::size_t channels, float wet) noexcept {
        if (!original || !processed || !output || channels == 0 || channels > 8 ||
            frames > (std::numeric_limits<std::size_t>::max() / channels) ||
            !std::isfinite(wet) || wet < 0.f || wet > 1.f) return false;
        const float dry = std::cos(wet * 1.5707963267948966f);
        const float mix = std::sin(wet * 1.5707963267948966f);
        const auto count = frames * channels;
        // Validate first: no partial buffer changes if input contains invalid PCM.
        for (std::size_t i=0;i<count;++i)
            if (!std::isfinite(original[i]) || !std::isfinite(processed[i])) return false;
        for (std::size_t i=0;i<count;++i)
            output[i] = original[i]*dry + processed[i]*mix;
        return true;
    }
};
}
