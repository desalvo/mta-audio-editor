// r101-r120: explicit activation preflight, control thread only. No realtime I/O.
#pragma once
#include "vst3_worker_runtime.hpp"
#include <array>
#include <cstddef>
#include <cstdint>
#include <limits>
namespace mta {
enum class ReadinessCheck : std::uint8_t {
  quantum, channels, rate, queue_min, queue_max, lookahead_min, lookahead_capacity,
  idle_min, idle_max, callback_quiescent, ipc_handshake, ipc_version, plugin_loaded,
  process_verified, latency_reported, fault_recovery, midi_verified,
  automation_verified, platforms_verified, realtime_stress_verified
};
struct NativeHostEvidence {
  bool callback_quiescent = false;
  bool ipc_handshake = false;
  bool ipc_version = false;
  bool plugin_loaded = false;
  bool process_verified = false;
  bool latency_reported = false;
  bool fault_recovery = false;
  bool midi_verified = false;
  bool automation_verified = false;
  bool platforms_verified = false;
  bool realtime_stress_verified = false;
};
struct ReadinessReport {
  std::array<bool,20> passed{};
  std::size_t passed_count() const noexcept {
    std::size_t total=0; for(bool item:passed) if(item) ++total; return total;
  }
  bool ready_for_review() const noexcept { return passed_count()==passed.size(); }
  bool passed_check(ReadinessCheck check) const noexcept {
    const auto i=static_cast<std::size_t>(check);
    return i<passed.size() && passed[i];
  }
};
inline ReadinessReport validate_native_host(const WorkerRuntimeConfig& c,
                                            const NativeHostEvidence& e) noexcept {
  ReadinessReport r{};
  r.passed = {{
    c.quantum.frames>=1 && c.quantum.frames<=kMaxBlockFrames,
    c.quantum.channels==1 || c.quantum.channels==2,
    c.quantum.rate==44100 || c.quantum.rate==48000 || c.quantum.rate==96000,
    c.queue_blocks>=3,
    c.queue_blocks<=4096,
    c.lookahead_blocks>=1,
    c.lookahead_blocks<c.queue_blocks,
    c.max_idle_spins>=1,
    c.max_idle_spins<=4096,
    e.callback_quiescent,
    e.ipc_handshake,
    e.ipc_version,
    e.plugin_loaded,
    e.process_verified,
    e.latency_reported,
    e.fault_recovery,
    e.midi_verified,
    e.automation_verified,
    e.platforms_verified,
    e.realtime_stress_verified
  }};
  return r;
}
// Deliberately separate diagnostic readiness from the production enable switch.
// Even passing all 20 checks never turns on native_host_ready by itself.
inline constexpr bool kNativeHostActivationAllowed = false;
} // namespace mta
