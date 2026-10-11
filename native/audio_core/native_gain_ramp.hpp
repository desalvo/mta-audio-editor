// Realtime safe click-reduction gain ramp. No allocation and no exceptions.
#pragma once
#include <cmath>
#include <cstddef>
namespace mta {
class NativeGainRamp {
  float current_ = 1.0f;
public:
  float current() const noexcept { return current_; }
  bool reset(float gain) noexcept {
    if (!std::isfinite(gain) || gain < 0.0f || gain > 16.0f) return false;
    current_ = gain; return true;
  }
  bool process(const float* input, float* output, std::size_t frames,
               std::size_t channels, float target) noexcept {
    if (!input || !output || input == output || frames == 0 || frames > 512 ||
        (channels != 1 && channels != 2) || !std::isfinite(target) ||
        target < 0.0f || target > 16.0f) return false;
    for (std::size_t n=0;n<frames*channels;++n)
      if (!std::isfinite(input[n])) return false;
    const float step = (target-current_) / static_cast<float>(frames);
    for (std::size_t frame=0;frame<frames;++frame) {
      const float gain = current_ + step * static_cast<float>(frame+1);
      for (std::size_t ch=0;ch<channels;++ch)
        output[frame*channels+ch] = input[frame*channels+ch]*gain;
    }
    current_=target; return true;
  }
};
}
