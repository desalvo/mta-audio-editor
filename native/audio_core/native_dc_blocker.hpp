// Preallocated per-channel DC rejection filter for realtime native PCM paths.
// Prepare/reset outside playback or while the processing graph is stopped.
#pragma once
#include <array>
#include <cmath>
#include <cstddef>
namespace mta {
class NativeDcBlocker final {
 public:
  static constexpr std::size_t max_channels = 8;
  explicit NativeDcBlocker(std::size_t channels, float pole = 0.995f) noexcept
      : channels_(channels), pole_(pole), ready_(channels > 0 && channels <= max_channels && std::isfinite(pole) && pole >= 0.0f && pole < 1.0f) {}
  bool valid() const noexcept { return ready_; }
  void reset() noexcept { previous_in_.fill(0.0f); previous_out_.fill(0.0f); }
  bool process(float* interleaved, std::size_t frames) noexcept {
    if (!ready_ || !interleaved || frames == 0 || frames > 512) return false;
    for (std::size_t i = 0; i < frames * channels_; ++i)
      if (!std::isfinite(interleaved[i])) return false;
    for (std::size_t i = 0; i < frames; ++i)
      for (std::size_t ch = 0; ch < channels_; ++ch) {
        const std::size_t index = i * channels_ + ch;
        const float x = interleaved[index];
        const float y = x - previous_in_[ch] + pole_ * previous_out_[ch];
        previous_in_[ch] = x;
        previous_out_[ch] = std::isfinite(y) ? y : 0.0f;
        interleaved[index] = previous_out_[ch];
      }
    return true;
  }
 private:
  std::size_t channels_;
  float pole_;
  bool ready_;
  std::array<float, max_channels> previous_in_{};
  std::array<float, max_channels> previous_out_{};
};
}
