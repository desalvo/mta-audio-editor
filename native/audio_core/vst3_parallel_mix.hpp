// Experimental native wet/dry alignment. Configure on control thread; process on audio thread.
// This is not wired to production playback and does not enable the VST3 host.
#pragma once
#include "vst3_latency_line.hpp"
#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
namespace mta {
class Vst3ParallelMix final {
public:
  Vst3ParallelMix(std::size_t plugin_latency_frames, std::size_t channels) noexcept
    : dry_delay_(plugin_latency_frames, channels), channels_(channels) {}
  bool valid() const noexcept { return dry_delay_.valid(); }
  // wet == nullptr represents plugin timeout/crash: emit latency-aligned dry.
  // Mix is clamped to [0, 1]. No heap allocation or lock in this method.
  // A separate preallocated per-block buffer permits in-place output; wet must
  // not alias out because dry alignment is processed before combining wet.
  bool process(const float* dry, const float* wet, float* out, std::size_t frames,
               std::size_t channels, float mix) noexcept {
    if (!valid() || !dry || !out || frames == 0 || frames > 512 ||
        channels != channels_ || !std::isfinite(mix) ||
        (wet && wet == out)) return false;
    const auto samples = frames * channels;
    // Reject invalid data before advancing any delay state.
    for (std::size_t i=0; i<samples; ++i) {
      if (!std::isfinite(dry[i]) || (wet && !std::isfinite(wet[i]))) {
        std::fill_n(out,samples,0.f);
        return false;
      }
    }
    if (!dry_delay_.process(dry, aligned_.data(), frames, channels)) return false;
    const float gain = wet ? std::clamp(mix,0.f,1.f) : 0.f;
    for (std::size_t i=0; i<samples; ++i)
      out[i] = aligned_[i] * (1.f-gain) + (wet ? wet[i]*gain : 0.f);
    return true;
  }
  void reset() noexcept { dry_delay_.reset(); } // callback quiescent only
private:
  Vst3LatencyLine dry_delay_;
  std::size_t channels_;
  std::array<float,1024> aligned_{};
};
}
