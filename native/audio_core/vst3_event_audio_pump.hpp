// Experimental worker-thread coupling of PCM and MIDI/automation packets.
// The SDK-backed EventSink and audio processor must be implemented by the host;
// this adapter deliberately never runs on the realtime callback.
#pragma once
#include "vst3_event_dispatch.hpp"
#include "vst3_worker_events.hpp"
#include "vst3_playout_bridge.hpp"
#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
namespace mta {
struct EventAudioPumpStats {
  std::uint64_t processed=0, silent_event_blocks=0, rejected_events=0;
  std::uint64_t processor_failures=0, output_full=0;
};
class Vst3EventAudioPump final {
public:
  Vst3EventAudioPump(Vst3PlayoutBridge& pcm, Vst3WorkerEvents& events,
                     std::uint64_t epoch) noexcept
    : pcm_(pcm), events_(events), dispatcher_(epoch), epoch_(epoch) {}
  const EventAudioPumpStats& stats() const noexcept { return stats_; }
  // Called on CONTROL thread after worker has stopped and queues are quiescent.
  bool reset(std::uint64_t epoch) noexcept {
    if (!dispatcher_.reset(epoch)) return false;
    epoch_=epoch;
    return true;
  }
  template<class Processor> bool pump_once(EventSink& sink, Processor&& process) {
    std::uint64_t seq=0;
    std::size_t frames=0, channels=0;
    if (!pcm_.worker_take(seq, input_.data(), input_.size(), frames, channels)) return false;
    Vst3EventPacket packet;
    if (!packet.initialize(epoch(), seq, frames)) { ++stats_.rejected_events; return true; }
    Vst3EventPacket queued;
    const auto take = events_.take_for_checked(epoch(), seq, frames, queued);
    if (take == EventTakeResult::matched) packet=queued;
    else if (take == EventTakeResult::empty) ++stats_.silent_event_blocks;
    else { ++stats_.rejected_events; return true; }
    // No processing if the event dispatch failed: never process audio against
    // an inconsistent MIDI/automation timeline.
    if (!dispatcher_.dispatch(packet, sink)) { ++stats_.rejected_events; return true; }
    std::fill_n(output_.data(), frames*channels, 0.0f);
    bool ok=false;
    try { ok=static_cast<bool>(process(input_.data(),output_.data(),frames,channels)); }
    catch (...) { ok=false; }
    if (ok) for (std::size_t i=0;i<frames*channels;++i)
      if (!std::isfinite(output_[i])) {ok=false;break;}
    if (!ok) { ++stats_.processor_failures; return true; }
    if (!pcm_.worker_return(seq,output_.data(),frames,channels)) ++stats_.output_full;
    else ++stats_.processed;
    return true;
  }
private:
  std::uint64_t epoch() const noexcept { return epoch_; }
  Vst3PlayoutBridge& pcm_;
  Vst3WorkerEvents& events_;
  EventDispatcher dispatcher_;
  std::uint64_t epoch_ = 1;
  std::array<float,kMaxBlockFrames*kMaxBlockChannels> input_{};
  std::array<float,kMaxBlockFrames*kMaxBlockChannels> output_{};
  EventAudioPumpStats stats_{};
};
}
