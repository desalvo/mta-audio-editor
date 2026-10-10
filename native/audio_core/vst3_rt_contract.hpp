// Experimental control-plane utilities for the native VST3 bridge.
// Configure on a non-audio thread; callback processing never uses this API.
#pragma once
#include "block_spsc.hpp"
#include <algorithm>
#include <array>
#include <atomic>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <limits>

namespace mta {
// r78: immutable quantum negotiated before transport starts.
struct Vst3Quantum {
  std::uint16_t frames = 0;
  std::uint8_t channels = 0;
  std::uint32_t rate = 0;
  bool valid() const noexcept { return frames >= 1 && frames <= kMaxBlockFrames &&
    (channels == 1 || channels == 2) && (rate == 44100 || rate == 48000 || rate == 96000); }
  bool accepts(std::size_t f, std::size_t c) const noexcept {
    return valid() && f == frames && c == channels;
  }
};
// r79: epoch tagging rejects responses from earlier seek / stop / restart.
struct Vst3Token {
  std::uint64_t epoch = 0;
  std::uint64_t sequence = 0;
  bool same_session(const Vst3Token& other) const noexcept { return epoch == other.epoch; }
};
class EpochClock final {
public:
  std::uint64_t current() const noexcept { return epoch_.load(std::memory_order_acquire); }
  // Caller must stop and join the worker before resetting queues; never callback.
  std::uint64_t restart() noexcept { return epoch_.fetch_add(1, std::memory_order_acq_rel) + 1; }
  bool accepts(const Vst3Token& token) const noexcept { return token.epoch == current(); }
private:
  std::atomic<std::uint64_t> epoch_{1};
};
// r80: bounded monotonic worker deadline, in audio frames (no realtime clock syscall).
class FrameDeadline final {
public:
  FrameDeadline(std::uint64_t submitted, std::uint32_t budget) noexcept
      : expiration_(submitted > std::numeric_limits<std::uint64_t>::max() - budget ?
        std::numeric_limits<std::uint64_t>::max() : submitted + budget) {}
  bool expired(std::uint64_t playback_frame) const noexcept { return playback_frame > expiration_; }
  std::uint64_t expiration() const noexcept { return expiration_; }
private:
  std::uint64_t expiration_;
};
// r81: explicit plugin + scheduling latency planning, saturating on overflow.
struct NativeLatencyBudget {
  std::uint32_t plugin_frames = 0;
  std::uint32_t lookahead_blocks = 0;
  std::uint32_t quantum_frames = 0;
  std::uint64_t total_frames() const noexcept {
    return static_cast<std::uint64_t>(plugin_frames) +
           static_cast<std::uint64_t>(lookahead_blocks) * quantum_frames;
  }
  std::uint64_t alignment_to(const NativeLatencyBudget& other) const noexcept {
    return other.total_frames() > total_frames() ? other.total_frames() - total_frames() : 0;
  }
};
// r82: finite, bounded dry fallback gain with deterministic ramp, no allocation.
class BypassRamp final {
public:
  explicit BypassRamp(std::size_t samples) noexcept : duration_(samples ? samples : 1) {}
  void set_bypass(bool bypass) noexcept { target_ = bypass ? 1.0f : 0.0f; }
  float next() noexcept {
    if (value_ < target_) value_ = std::min(target_, value_ + 1.0f / duration_);
    else if (value_ > target_) value_ = std::max(target_, value_ - 1.0f / duration_);
    return value_;
  }
  float mix(float wet, float dry) noexcept {
    return std::isfinite(wet) && std::isfinite(dry) ? wet * (1.0f-next()) + dry * value_ : 0.0f;
  }
private:
  const float duration_;
  float value_ = 0.0f;
  float target_ = 0.0f;
};
// r83: finite, valid parameter events with stable ordering and bounded storage.
struct NativeParameterEvent { std::uint32_t parameter = 0; std::uint16_t offset = 0; float value = 0; };
class ParameterBlock final {
public:
  bool add(std::uint32_t id, std::uint16_t offset, float value, std::size_t frames) noexcept {
    if (used_ == values_.size() || offset >= frames || !std::isfinite(value) || value < 0 || value > 1) return false;
    if (used_ && offset < values_[used_-1].offset) return false;
    values_[used_++] = {id, offset, value}; return true;
  }
  const NativeParameterEvent* data() const noexcept { return values_.data(); }
  std::size_t size() const noexcept { return used_; }
  void clear() noexcept { used_ = 0; }
private:
  std::array<NativeParameterEvent, 128> values_{};
  std::size_t used_ = 0;
};
// r84: sample accurate bounded MIDI packets on the worker control plane.
struct NativeMidiEvent { std::uint16_t offset = 0; std::uint8_t status = 0, data1 = 0, data2 = 0; };
class MidiBlock final {
public:
  bool add(std::size_t offset, std::uint8_t status, std::uint8_t data1,
           std::uint8_t data2, std::size_t frames) noexcept {
    if (used_ == events_.size() || offset >= frames || (status & 0x80) == 0 ||
        (status & 0xf0) == 0xf0 || data1 > 127 || data2 > 127 ||
        (used_ && offset < events_[used_-1].offset)) return false;
    events_[used_++] = {static_cast<std::uint16_t>(offset), status, data1, data2}; return true;
  }
  std::size_t size() const noexcept { return used_; }
  const NativeMidiEvent* data() const noexcept { return events_.data(); }
  void clear() noexcept { used_ = 0; }
private:
  std::array<NativeMidiEvent, 256> events_{};
  std::size_t used_ = 0;
};
// r85: fault circuit-breaker; worker only updates, callback only reads snapshot.
class WorkerFaultGate final {
public:
  void fault() noexcept { failed_.store(true, std::memory_order_release); }
  bool failed() const noexcept { return failed_.load(std::memory_order_acquire); }
  // Only after stop + join + new worker instance, never from callback.
  void recover() noexcept { failed_.store(false, std::memory_order_release); }
private:
  std::atomic<bool> failed_{false};
};
// r86: clip protection and anomaly counting for offline worker boundary.
struct BlockValidation {
  std::uint64_t nonfinite = 0;
  std::uint64_t clipped = 0;
  bool sanitize(float* output, std::size_t frames, std::size_t channels) noexcept {
    if (!output || !frames || frames > kMaxBlockFrames || (channels != 1 && channels != 2)) return false;
    bool clean = true;
    for (std::size_t i=0; i<frames*channels; ++i) {
      if (!std::isfinite(output[i])) { ++nonfinite; output[i] = 0; clean = false; }
      else if (output[i] > 1.0f) { ++clipped; output[i] = 1.0f; }
      else if (output[i] < -1.0f) { ++clipped; output[i] = -1.0f; }
    }
    return clean;
  }
};
// r87: strict explicit readiness barrier, never enabled by these utilities.
inline constexpr bool kNativeVst3RealtimeReady = false;
} // namespace mta
