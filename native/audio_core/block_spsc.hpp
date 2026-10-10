// Bounded single-producer/single-consumer PCM block exchange. Experimental.
// Allocation is restricted to construction, never push/pop. One thread is the
// exclusive producer, another the exclusive consumer; never share roles.
#pragma once
#include <array>
#include <atomic>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <memory>
#include <new>

namespace mta {
constexpr std::size_t kMaxBlockFrames = 512;
constexpr std::size_t kMaxBlockChannels = 2;
struct AudioBlock {
  std::uint64_t sequence = 0;
  std::uint16_t frames = 0;
  std::uint8_t channels = 0;
  std::array<float, kMaxBlockFrames * kMaxBlockChannels> pcm{};
};

// SPSC capacity is the number of actual blocks, not sample slots.
class BlockSpsc final {
public:
  explicit BlockSpsc(std::size_t capacity) noexcept
      : capacity_(capacity >= 2 && capacity <= 4096 ? capacity : 0),
        storage_(capacity_ ? new (std::nothrow) AudioBlock[capacity_] : nullptr) {}
  BlockSpsc(const BlockSpsc&) = delete;
  BlockSpsc& operator=(const BlockSpsc&) = delete;
  bool valid() const noexcept { return storage_ != nullptr; }
  std::size_t capacity() const noexcept { return capacity_; }
  bool push(std::uint64_t sequence, const float* pcm, std::size_t frames,
            std::size_t channels) noexcept {
    if (!valid() || !pcm || !frames || frames > kMaxBlockFrames ||
        (channels != 1 && channels != 2)) return false;
    const auto count = frames * channels;
    for (std::size_t i = 0; i < count; ++i)
      if (!std::isfinite(pcm[i])) return false;
    const auto w = write_.load(std::memory_order_relaxed);
    const auto r = read_.load(std::memory_order_acquire);
    if (w - r >= capacity_) return false;
    auto& slot = storage_[w % capacity_];
    slot.sequence = sequence;
    slot.frames = static_cast<std::uint16_t>(frames);
    slot.channels = static_cast<std::uint8_t>(channels);
    for (std::size_t i = 0; i < count; ++i) slot.pcm[i] = pcm[i];
    write_.store(w + 1, std::memory_order_release);
    return true;
  }
  // Copies one complete block; never consumes if the caller's buffer is small.
  bool pop(std::uint64_t& sequence, float* pcm, std::size_t pcm_capacity,
           std::size_t& frames, std::size_t& channels) noexcept {
    if (!valid() || !pcm) return false;
    const auto r = read_.load(std::memory_order_relaxed);
    const auto w = write_.load(std::memory_order_acquire);
    if (r == w) return false;
    const auto& slot = storage_[r % capacity_];
    const auto count = static_cast<std::size_t>(slot.frames) * slot.channels;
    if (pcm_capacity < count) return false;
    for (std::size_t i = 0; i < count; ++i) pcm[i] = slot.pcm[i];
    sequence = slot.sequence;
    frames = slot.frames;
    channels = slot.channels;
    read_.store(r + 1, std::memory_order_release);
    return true;
  }
  std::size_t pending() const noexcept {
    return static_cast<std::size_t>(write_.load(std::memory_order_acquire) -
                                    read_.load(std::memory_order_acquire));
  }
private:
  const std::size_t capacity_;
  std::unique_ptr<AudioBlock[]> storage_;
  alignas(64) std::atomic<std::uint64_t> write_{0};
  alignas(64) std::atomic<std::uint64_t> read_{0};
};
}  // namespace mta
