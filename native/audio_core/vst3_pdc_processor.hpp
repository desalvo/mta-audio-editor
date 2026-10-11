// Experimental interleaved stereo PDC processor, control thread constructs, audio thread processes.
#pragma once
#include "vst3_pdc_plan.hpp"
#include "vst3_latency_line.hpp"
#include <array>
#include <memory>
#include <cstddef>
#include <algorithm>
#include <cmath>
namespace mta {
class Vst3PdcProcessor final {
public:
  explicit Vst3PdcProcessor(const Vst3PdcPlan& plan, std::size_t channels) noexcept
    : plan_(plan), channels_(channels) {
    if (!plan.valid || plan.count > kPdcMaxRoutes || (channels != 1 && channels != 2)) return;
    for (std::size_t i=0; i<plan.count; ++i) {
      if (!plan.routes[i].enabled) continue;
      lines_[i].reset(new (std::nothrow) Vst3LatencyLine(plan.routes[i].alignment_frames, channels));
      if (!lines_[i] || !lines_[i]->valid()) return;
    }
    ready_=true;
  }
  bool valid() const noexcept { return ready_; }
  std::size_t routes() const noexcept { return plan_.count; }
  std::uint32_t target_frames() const noexcept { return plan_.target_frames; }
  // inputs: one interleaved planar pointer per route. Enabled routes are averaged.
  // Buffer allocation is forbidden in this method. An input/output alias is rejected.
  bool process(const float* const* inputs, std::size_t input_count, float* output,
               std::size_t frames) noexcept {
    if (!ready_ || !inputs || !output || frames == 0 || frames > 512 || input_count != plan_.count) return false;
    const auto samples=frames*channels_;
    for (std::size_t r=0; r<input_count; ++r) {
      if (!plan_.routes[r].enabled) continue;
      if (!inputs[r] || inputs[r] == output) return false;
      for (std::size_t i=0;i<samples;++i) if (!std::isfinite(inputs[r][i])) return false;
    }
    std::fill_n(output,samples,0.0f);
    std::size_t active=0;
    std::array<float,1024> scratch{};
    for (std::size_t r=0; r<input_count; ++r) {
      if (!plan_.routes[r].enabled) continue;
      if (!lines_[r]->process(inputs[r],scratch.data(),frames,channels_)) return false;
      ++active;
      for (std::size_t i=0; i<samples; ++i) output[i]+=scratch[i];
    }
    if (active) for(std::size_t i=0;i<samples;++i) output[i]/=static_cast<float>(active);
    return true;
  }
  // Call only once the realtime audio callback is stopped.
  void reset() noexcept { for (auto& line: lines_) if (line) line->reset(); }
private:
  Vst3PdcPlan plan_;
  std::size_t channels_;
  std::array<std::unique_ptr<Vst3LatencyLine>,kPdcMaxRoutes> lines_{};
  bool ready_=false;
};
} // namespace mta
