// Experimental realtime-safe interleaved PCM sum with per-route gain and mute.
#pragma once
#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>
namespace mta {
struct NativeMixRoute { const float* input; float gain; bool enabled; };
// `routes` and buffers are caller-owned and stable during callback.
// Validates the entire input before touching the output: failure is atomic.
inline bool mix_native_pcm(const NativeMixRoute* routes, std::size_t count,
                           float* output, std::size_t frames, std::size_t channels) noexcept {
  if (!routes || !output || count == 0 || count > 64 || frames == 0 || frames > 512 ||
      (channels != 1 && channels != 2)) return false;
  const std::size_t n = frames * channels;
  for (std::size_t r=0; r<count; ++r) {
    if (!routes[r].enabled) continue;
    if (!routes[r].input || routes[r].input == output || !std::isfinite(routes[r].gain) ||
        std::fabs(routes[r].gain) > 16.0f) return false;
    for (std::size_t i=0; i<n; ++i) if (!std::isfinite(routes[r].input[i])) return false;
  }
  std::fill_n(output,n,0.0f);
  for (std::size_t r=0; r<count; ++r) {
    if (!routes[r].enabled || routes[r].gain == 0.0f) continue;
    for (std::size_t i=0; i<n; ++i) output[i] += routes[r].input[i] * routes[r].gain;
  }
  for (std::size_t i=0; i<n; ++i) if (!std::isfinite(output[i])) {
    std::fill_n(output,n,0.0f); return false;
  }
  return true;
}
} // namespace mta
