// Experimental native playout bridge; never calls a VST3 plugin or performs IPC
// on the audio callback. One callback producer/consumer, one worker consumer/producer.
#pragma once
#include "block_spsc.hpp"
#include <algorithm>
#include <array>
#include <atomic>
#include <cstddef>
#include <cstdint>
#include <cmath>
#include <memory>
#include <new>
#include <optional>

namespace mta {
struct PlayoutStats {
  std::uint64_t submitted = 0;
  std::uint64_t dropped = 0;
  std::uint64_t processed = 0;
  std::uint64_t bypassed = 0;
  std::uint64_t late = 0;
  std::uint64_t poll_budget_exhausted = 0;
};

class Vst3PlayoutBridge final {
public:
  Vst3PlayoutBridge(std::size_t queue_blocks, std::size_t lookahead,
                    std::size_t quantum_frames=0, std::size_t channels=0) noexcept
      : incoming_(queue_blocks), outgoing_(queue_blocks),
        lookahead_(lookahead >= 1 && lookahead < queue_blocks ? lookahead : 0),
        dry_(lookahead_ ? new (std::nothrow) AudioBlock[lookahead_ + 1] : nullptr),
        quantum_frames_(quantum_frames), negotiated_channels_(channels) {}
  bool valid() const noexcept { return incoming_.valid() && outgoing_.valid() && dry_ != nullptr; }
  // Called exclusively by audio callback. Output is delayed by lookahead blocks.
  // Before the pipeline is primed, outputs silence. On underrun use matched dry.
  // Inputs must have a constant channel count and frame length within one epoch.
  bool callback(const float* input, float* output, std::size_t frames,
                std::size_t channels) noexcept {
    if (!valid() || !input || !output || !frames || frames > kMaxBlockFrames ||
        (channels != 1 && channels != 2)) return false;
    if ((quantum_frames_ && frames != quantum_frames_) ||
        (negotiated_channels_ && channels != negotiated_channels_)) {
      std::fill_n(output, frames * channels, 0.0f);
      return false;
    }
    const auto count = frames * channels;
    // Invalid source samples must never enter the plugin or dry fallback.
    // Validation performs bounded work (<= 1024 samples), no allocations.
    for (std::size_t i = 0; i < count; ++i) {
      if (!std::isfinite(input[i])) {
        std::fill_n(output, count, 0.0f);
        return false;
      }
    }
    const auto sequence = next_++;
    auto& dry = dry_[sequence % (lookahead_ + 1)];
    dry.sequence = sequence;
    dry.frames = static_cast<std::uint16_t>(frames);
    dry.channels = static_cast<std::uint8_t>(channels);
    for (std::size_t i = 0; i < count; ++i) dry.pcm[i] = input[i];
    if (incoming_.push(sequence, input, frames, channels)) ++stats_.submitted;
    else ++stats_.dropped;
    if (sequence < lookahead_) {
      std::fill_n(output, count, 0.0f);
      return true;
    }
    const auto wanted = sequence - lookahead_;
    // Consume old results, but never allow one into a newer playout slot.
    std::uint64_t result_sequence = 0;
    std::size_t result_frames = 0, result_channels = 0;
    bool matched = false;
    // A single outstanding "future" result is kept in a preallocated slot.
    const auto& original = dry_[wanted % (lookahead_ + 1)];
    const bool dry_matches = original.sequence == wanted;
    if (future_ && future_->sequence == wanted && dry_matches &&
        future_->frames == original.frames && future_->channels == original.channels &&
        original.frames == frames && original.channels == channels) {
      for (std::size_t i = 0; i < original.frames * original.channels; ++i) output[i] = future_->pcm[i];
      future_.reset();
      matched = true;
    } else if (future_ && future_->sequence <= wanted) {
      future_.reset(); ++stats_.late;
    }
    // Hard upper bound on queue operations per callback invocation. A stalled
    // worker can accumulate stale results; never let them extend audio deadline.
    constexpr std::size_t kMaxResultPollsPerCallback = 8;
    std::size_t result_polls = 0;
    while (!matched && !future_ && result_polls < kMaxResultPollsPerCallback &&
           outgoing_.pop(result_sequence, scratch_.data(), scratch_.size(),
                         result_frames, result_channels)) {
      ++result_polls;
      if (result_sequence < wanted) { ++stats_.late; continue; }
      if (result_sequence > wanted) {
        future_.emplace();
        future_->sequence = result_sequence;
        future_->frames = static_cast<std::uint16_t>(result_frames);
        future_->channels = static_cast<std::uint8_t>(result_channels);
        std::copy_n(scratch_.data(), result_frames * result_channels, future_->pcm.data());
        break;
      }
      if (dry_matches && result_frames == original.frames && result_channels == original.channels &&
          original.frames == frames && original.channels == channels) {
        std::copy_n(scratch_.data(), result_frames * result_channels, output);
        matched = true;
      }
    }
    if (!matched && !future_ && result_polls == kMaxResultPollsPerCallback)
      ++stats_.poll_budget_exhausted;
    // Variable-size callbacks cannot represent a delayed block of a different
    // shape in their output buffer. In that case emit silence instead of
    // writing beyond the caller-provided buffer. The native engine must
    // negotiate a fixed playback quantum before enabling this path.
    if (dry_matches && (original.frames != frames || original.channels != channels)) {
      std::fill_n(output, count, 0.0f);
      if (matched) ++stats_.processed;
      else ++stats_.bypassed;
      return true;
    }
    if (matched) ++stats_.processed;
    else {
      ++stats_.bypassed;
      if (dry_matches)
        std::copy_n(original.pcm.data(), original.frames * original.channels, output);
      else std::fill_n(output, count, 0.0f);
    }
    return true;
  }
  // Worker thread only: processing must happen outside the callback.
  bool worker_take(std::uint64_t& sequence, float* out, std::size_t capacity,
                   std::size_t& frames, std::size_t& channels) noexcept {
    return incoming_.pop(sequence, out, capacity, frames, channels);
  }
  bool worker_return(std::uint64_t sequence, const float* pcm,
                     std::size_t frames, std::size_t channels) noexcept {
    return outgoing_.push(sequence, pcm, frames, channels);
  }
  PlayoutStats stats() const noexcept { return stats_; } // callback thread only
private:
  BlockSpsc incoming_;
  BlockSpsc outgoing_;
  const std::size_t lookahead_;
  std::unique_ptr<AudioBlock[]> dry_;
  const std::size_t quantum_frames_, negotiated_channels_;
  std::uint64_t next_ = 0;
  PlayoutStats stats_{};
  std::array<float, kMaxBlockFrames * kMaxBlockChannels> scratch_{};
  std::optional<AudioBlock> future_{};
};
} // namespace mta
