// Experimental control-thread path delay compensation planner.
// Produces per-route delay in frames; allocate delay lines before audio callbacks.
#pragma once
#include <array>
#include <cstddef>
#include <cstdint>
#include <limits>

namespace mta {
constexpr std::size_t kPdcMaxRoutes = 64;
constexpr std::uint32_t kPdcMaxDelayFrames = 1048576;
struct Vst3PdcRoute {
  std::uint32_t plugin_frames = 0;
  std::uint32_t ipc_frames = 0;
  std::uint32_t alignment_frames = 0;
  bool enabled = true;
};
struct Vst3PdcPlan {
  std::array<Vst3PdcRoute, kPdcMaxRoutes> routes{};
  std::size_t count = 0;
  std::uint32_t target_frames = 0;
  bool valid = false;
};
// Fail closed on invalid configuration and overflow; no runtime allocation.
inline Vst3PdcPlan make_vst3_pdc_plan(const Vst3PdcRoute* routes, std::size_t count) noexcept {
  Vst3PdcPlan result;
  if ((!routes && count) || count > kPdcMaxRoutes) return result;
  result.count = count;
  for (std::size_t i = 0; i < count; ++i) {
    const auto& source = routes[i];
    const auto sum = static_cast<std::uint64_t>(source.plugin_frames) + source.ipc_frames;
    if (source.enabled && sum > kPdcMaxDelayFrames) return Vst3PdcPlan{};
    result.routes[i] = source;
    if (source.enabled && sum > result.target_frames) result.target_frames = static_cast<std::uint32_t>(sum);
  }
  for (std::size_t i = 0; i < count; ++i) {
    auto& route = result.routes[i];
    route.alignment_frames = route.enabled ? result.target_frames - (route.plugin_frames + route.ipc_frames) : 0;
  }
  result.valid = true;
  return result;
}
} // namespace mta
