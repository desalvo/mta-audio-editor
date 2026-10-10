// Experimental control-thread latency policy: compose plugin and IPC latency.
#pragma once
#include "vst3_rt_contract.hpp"
#include <cstdint>
#include <limits>
namespace mta {
struct Vst3LatencyPolicy {
  std::uint32_t plugin_frames=0, quantum_frames=0, lookahead_blocks=0;
  bool valid() const noexcept {
    return quantum_frames>=1 && quantum_frames<=kMaxBlockFrames &&
      lookahead_blocks>=1 && lookahead_blocks<=32 && plugin_frames<=1048576;
  }
  std::uint64_t wet_arrival_frames() const noexcept {
    return static_cast<std::uint64_t>(quantum_frames)*lookahead_blocks;
  }
  // Host must compensate whichever path arrives first, including algorithmic plugin latency.
  std::uint64_t dry_delay_frames() const noexcept {
    return valid() ? wet_arrival_frames()+plugin_frames : 0;
  }
  bool fits_delay_line() const noexcept { return valid() && dry_delay_frames()<=1048576; }
  std::uint64_t relative_delay_to(const Vst3LatencyPolicy& other) const noexcept {
    if (!valid() || !other.valid()) return 0;
    const auto ours=dry_delay_frames(), theirs=other.dry_delay_frames();
    return theirs>ours ? theirs-ours : 0;
  }
};
} // namespace mta
