// Experimental bounded worker-side MIDI/automation transport. NOT attached to
// the VST3 SDK yet. Producer and consumer each require exclusive ownership.
#pragma once
#include "vst3_event_packet.hpp"
#include <atomic>
#include <cstddef>
#include <cstdint>
#include <memory>
#include <new>

namespace mta {
enum class EventTakeResult : std::uint8_t { empty, matched, invalid_shape, scan_limit };
class Vst3WorkerEvents final {
public:
  explicit Vst3WorkerEvents(std::size_t capacity) noexcept
    : capacity_(capacity >= 2 && capacity <= 256 ? capacity : 0),
      entries_(capacity_ ? new (std::nothrow) Vst3EventPacket[capacity_] : nullptr) {}
  Vst3WorkerEvents(const Vst3WorkerEvents&) = delete;
  Vst3WorkerEvents& operator=(const Vst3WorkerEvents&) = delete;
  bool valid() const noexcept { return entries_ != nullptr; }
  // r138: enqueue prepared packets without allocating or taking a mutex.
  bool push(const Vst3EventPacket& packet) noexcept {
    if (!valid() || packet.epoch == 0 || packet.frames == 0 ||
        packet.frames > kMaxBlockFrames) return false;
    const auto w = write_.load(std::memory_order_relaxed);
    const auto r = read_.load(std::memory_order_acquire);
    if (w-r >= capacity_) return false;
    entries_[w%capacity_] = packet;
    write_.store(w+1, std::memory_order_release);
    return true;
  }
  // r139: reject stale packets from an earlier transport epoch or sequence.
  // Scan bounded to `max_scans` so a stalled consumer cannot spin indefinitely.
  // Worker only. Never silently turn a malformed packet for the exact PCM
  // block into an eventless block: the caller must reject that PCM block.
  EventTakeResult take_for_checked(std::uint64_t epoch, std::uint64_t sequence,
                std::size_t frames, Vst3EventPacket& output,
                std::size_t max_scans = 8) noexcept {
    if (!valid() || !epoch || !frames || max_scans == 0)
      return EventTakeResult::invalid_shape;
    for (std::size_t scanned=0; scanned<max_scans; ++scanned) {
      const auto r=read_.load(std::memory_order_relaxed);
      const auto w=write_.load(std::memory_order_acquire);
      if (r==w) return EventTakeResult::empty;
      const auto& p=entries_[r%capacity_];
      if (p.epoch > epoch || (p.epoch == epoch && p.sequence > sequence))
        return EventTakeResult::empty;
      if (p.epoch == epoch && p.sequence == sequence) {
        if (p.frames != frames) {
          read_.store(r+1,std::memory_order_release);
          return EventTakeResult::invalid_shape;
        }
        output=p;
        read_.store(r+1,std::memory_order_release);
        return EventTakeResult::matched;
      }
      read_.store(r+1,std::memory_order_release);
    }
    // A backlog of stale events may hide an exact-match packet. Fail closed
    // instead of processing the audio as if it had no events.
    return EventTakeResult::scan_limit;
  }
  // Legacy boolean API for existing consumers.
  bool take_for(std::uint64_t epoch, std::uint64_t sequence,
                std::size_t frames, Vst3EventPacket& output,
                std::size_t max_scans = 8) noexcept {
    return take_for_checked(epoch,sequence,frames,output,max_scans)
           == EventTakeResult::matched;
  }
  std::size_t pending() const noexcept {
    return static_cast<std::size_t>(write_.load(std::memory_order_acquire)-
                                    read_.load(std::memory_order_acquire));
  }
private:
  const std::size_t capacity_;
  std::unique_ptr<Vst3EventPacket[]> entries_;
  alignas(64) std::atomic<std::uint64_t> write_{0};
  alignas(64) std::atomic<std::uint64_t> read_{0};
};
} // namespace mta
