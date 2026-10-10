// Offline / worker-thread-only adapter. Never call pump_once on the audio callback.
#pragma once
#include "vst3_playout_bridge.hpp"
#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <cmath>
#include <utility>

namespace mta {
struct WorkerPumpStats {
  std::uint64_t handled = 0;
  std::uint64_t processing_failures = 0;
  std::uint64_t output_overruns = 0;
  std::uint64_t processor_exceptions = 0;
};

class Vst3WorkerPump final {
public:
  explicit Vst3WorkerPump(Vst3PlayoutBridge& bridge) noexcept : bridge_(bridge) {}
  // Processor must have signature:
  // bool(float const* input, float* output, size_t frames, size_t channels)
  // Processing can perform IPC and block: this method is worker-thread-only.
  template<class Processor> bool pump_once(Processor&& process) {
    std::uint64_t sequence = 0;
    std::size_t frames = 0, channels = 0;
    if (!bridge_.worker_take(sequence, input_.data(), input_.size(), frames, channels))
      return false;
    // Never let unwritten samples from a previous block leak into a new result.
    // The processor contract requires a complete output block; clearing also
    // makes a partially writing faulty processor fail safely as silence.
    std::fill_n(output_.data(), frames * channels, 0.0f);
    // r136: plugin adapter exceptions must never escape and kill the worker loop.
    bool success = false;
    try { success = static_cast<bool>(process(input_.data(), output_.data(), frames, channels)); }
    catch (...) { ++stats_.processor_exceptions; }
    if (!success) {
      ++stats_.processing_failures;
      return true; // the audio callback will use its delayed dry fallback
    }
    // r137: all returned samples must be finite before they enter the output queue.
    for (std::size_t i = 0; i < frames * channels; ++i) {
      if (!std::isfinite(output_[i])) {
        ++stats_.processing_failures;
        return true;
      }
    }
    if (!bridge_.worker_return(sequence, output_.data(), frames, channels))
      ++stats_.output_overruns;
    else ++stats_.handled;
    return true;
  }
  WorkerPumpStats stats() const noexcept { return stats_; } // worker thread only
private:
  Vst3PlayoutBridge& bridge_;
  std::array<float, kMaxBlockFrames * kMaxBlockChannels> input_{};
  std::array<float, kMaxBlockFrames * kMaxBlockChannels> output_{};
  WorkerPumpStats stats_{};
};
}
