// Experimental fixed-capacity event packet; prepare before submitting audio.
// Consumer is the worker thread, NOT the realtime callback or current SDK host.
#pragma once
#include "vst3_rt_contract.hpp"
#include <cstddef>
#include <cstdint>
namespace mta {
struct Vst3EventPacket final {
  std::uint64_t epoch=0, sequence=0;
  std::size_t frames=0;
  MidiBlock midi{};
  ParameterBlock automation{};
  bool initialize(std::uint64_t epoch_id,std::uint64_t seq,std::size_t quantum) noexcept {
    if (!epoch_id || quantum==0 || quantum>kMaxBlockFrames) return false;
    epoch=epoch_id; sequence=seq; frames=quantum; midi.clear(); automation.clear();
    return true;
  }
  bool note(std::size_t offset,std::uint8_t status,std::uint8_t pitch,std::uint8_t velocity) noexcept {
    return frames && midi.add(offset,status,pitch,velocity,frames);
  }
  bool parameter(std::uint32_t id,std::size_t offset,float value) noexcept {
    return frames && automation.add(id,static_cast<std::uint16_t>(offset),value,frames);
  }
  bool matches(std::uint64_t e,std::uint64_t s,std::size_t quantum) const noexcept {
    return epoch==e && sequence==s && frames==quantum;
  }
};
} // namespace mta
