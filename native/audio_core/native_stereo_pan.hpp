// Experimental click-free stereo pan ramp; caller-owned interleaved float PCM.
#pragma once
#include <cmath>
#include <cstddef>
namespace mta::audio {
struct StereoPanRamp {
  float current=0.0f;
  bool process(float* data, std::size_t frames, float target) noexcept {
    if (!data || frames == 0 || frames > 4096 || !std::isfinite(current) ||
        !std::isfinite(target) || target < -1.f || target > 1.f ||
        current < -1.f || current > 1.f) return false;
    for (std::size_t i=0;i<frames;++i) {
      const float p=current+(target-current)*float(i+1)/float(frames);
      // Linear pan preserves L/R at center.
      const float left=(p>0.f)?1.f-p:1.f;
      const float right=(p<0.f)?1.f+p:1.f;
      float &l=data[2*i], &r=data[2*i+1];
      if (!std::isfinite(l) || !std::isfinite(r)) {l=0.f;r=0.f;}
      l*=left; r*=right;
    }
    current=target;return true;
  }
};
}
