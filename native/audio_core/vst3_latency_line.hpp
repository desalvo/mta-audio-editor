// Experimental fixed-delay dry-path alignment for native VST3 playout.
// Construction/configuration on control thread. process() on audio thread only.
#pragma once
#include <algorithm>
#include <cstddef>
#include <cmath>
#include <memory>
#include <new>

namespace mta {
class Vst3LatencyLine final {
public:
  // Delay is in audio frames, independently of channel count / callback quantum.
  Vst3LatencyLine(std::size_t delay_frames, std::size_t channels) noexcept
      : delay_(delay_frames), channels_(channels),
        size_(delay_frames <= 1048576 && (channels == 1 || channels == 2)
              ? (delay_frames ? delay_frames : 1) * channels : 0),
        data_(size_ && (channels == 1 || channels == 2)
                  ? new (std::nothrow) float[size_]{} : nullptr) {}
  bool valid() const noexcept { return data_ != nullptr && delay_ <= 1048576; }
  std::size_t delay_frames() const noexcept { return delay_; }
  // True for successfully processed samples; false and zeros output on invalid input.
  // No allocation, synchronization, IPC, or exceptions in this audio-thread method.
  bool process(const float* in, float* out, std::size_t frames, std::size_t channels) noexcept {
    if (!valid() || !in || !out || channels != channels_ || frames > 512 || frames == 0)
      return false;
    const auto samples = frames * channels;
    for (std::size_t i=0;i<samples;++i) {
      if (!std::isfinite(in[i])) {
        std::fill_n(out,samples,0.f);
        return false;
      }
    }
    // Works in-place. Writes the delayed sample before overwriting the ring slot.
    for (std::size_t f=0;f<frames;++f) {
      for (std::size_t c=0;c<channels;++c) {
        const auto idx=(cursor_*channels)+c;
        const auto input=in[f*channels+c];
        const auto delayed=data_[idx];
        data_[idx]=input;
        out[f*channels+c]=delay_ ? delayed : input;
      }
      if (++cursor_ >= (delay_ ? delay_ : 1)) cursor_=0;
    }
    return true;
  }
  // Reset ONLY while audio callback is quiescent (seek, stop, reconfiguration).
  void reset() noexcept {
    if (valid()) std::fill_n(data_.get(),size_,0.f);
    cursor_=0;
  }
private:
  const std::size_t delay_,channels_,size_;
  std::unique_ptr<float[]> data_;
  std::size_t cursor_=0;
};
} // namespace mta
