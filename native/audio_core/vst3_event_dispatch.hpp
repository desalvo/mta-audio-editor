// Worker-thread event dispatch boundary. Never call from the realtime callback.
#pragma once
#include "vst3_event_packet.hpp"
#include <cstdint>
#include <cstddef>
#include <limits>
namespace mta {
struct EventDispatchStats { std::uint64_t accepted=0, stale=0, future=0, invalid=0, midi=0, automation=0, delivery_failures=0; };
// Sink is called only from the worker thread. An SDK-backed sink can translate
// note events and normalized parameter values into Steinberg input queues.
class EventSink {
public:
  virtual ~EventSink() = default;
  virtual bool midi(const NativeMidiEvent&) noexcept = 0;
  virtual bool parameter(const NativeParameterEvent&) noexcept = 0;
};
class EventDispatcher final {
public:
  explicit EventDispatcher(std::uint64_t epoch) noexcept : epoch_(epoch) {}
  bool valid() const noexcept { return epoch_ != 0; }
  // Lifecycle / seek reset is a CONTROL-THREAD operation after worker join.
  bool reset(std::uint64_t new_epoch) noexcept {
    if (!new_epoch || new_epoch <= epoch_) return false;
    epoch_=new_epoch; next_=0; stats_={}; return true;
  }
  const EventDispatchStats& stats() const noexcept { return stats_; }
  std::uint64_t next_sequence() const noexcept { return next_; }
  // r141-150: epoch, ordering, bounds, validation, offset-preserving dispatch,
  // partial failure, deterministic advancement, safe no-event packets, reset.
  bool dispatch(const Vst3EventPacket& packet, EventSink& sink) noexcept {
    if (!valid() || packet.epoch == 0 || packet.frames == 0 || packet.frames > kMaxBlockFrames) {
      ++stats_.invalid; return false;
    }
    if (packet.epoch < epoch_ || (packet.epoch == epoch_ && packet.sequence < next_)) {
      ++stats_.stale; return false;
    }
    if (packet.epoch > epoch_ || packet.sequence > next_) {
      ++stats_.future; return false;
    }
    // Prevalidate the complete packet before emitting any events.
    std::size_t previous=0;
    for (std::size_t i=0; i<packet.midi.size(); ++i) {
      const auto& e=packet.midi.data()[i];
      if (e.offset>=packet.frames || (i && e.offset<previous) ||
          !(e.status & 0x80) || (e.status & 0xf0)==0xf0 ||
          e.data1>127 || e.data2>127) { ++stats_.invalid; return false; }
      previous=e.offset;
    }
    previous=0;
    for (std::size_t i=0; i<packet.automation.size(); ++i) {
      const auto& e=packet.automation.data()[i];
      if (e.offset>=packet.frames || (i && e.offset<previous) ||
          !(e.value>=0.0f && e.value<=1.0f)) { ++stats_.invalid; return false; }
      previous=e.offset;
    }
    bool delivered=true;
    for (std::size_t i=0; i<packet.midi.size(); ++i) {
      if (sink.midi(packet.midi.data()[i])) ++stats_.midi;
      else { ++stats_.delivery_failures; delivered=false; }
    }
    for (std::size_t i=0; i<packet.automation.size(); ++i) {
      if (sink.parameter(packet.automation.data()[i])) ++stats_.automation;
      else { ++stats_.delivery_failures; delivered=false; }
    }
    ++stats_.accepted;
    // Prevent wrap from making old packets eligible again.
    if (next_ == std::numeric_limits<std::uint64_t>::max()) { ++stats_.invalid; return false; }
    ++next_;
    return delivered;
  }
private:
  std::uint64_t epoch_;
  std::uint64_t next_=0;
  EventDispatchStats stats_{};
};
} // namespace mta
