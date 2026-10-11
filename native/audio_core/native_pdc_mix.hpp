// Experimental multiroute PCM mixer with preallocated VST3 latency compensation.
// Construct/prepare off the audio thread. Never mutate routes while processing.
#pragma once
#include "vst3_pdc_processor.hpp"
#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <memory>
#include <new>
namespace mta {
class NativePdcMix final {
public:
 explicit NativePdcMix(const Vst3PdcPlan& plan, std::size_t channels) noexcept
   : channels_(channels), pdc_(plan, channels), count_(plan.count) {
   if (!pdc_.valid() || count_==0 || count_>kPdcMaxRoutes) return;
   for(std::size_t i=0;i<count_;++i) { gains_[i]=1.0f; enabled_[i]=plan.routes[i].enabled; }
   ready_=true;
 }
 bool valid() const noexcept { return ready_; }
 bool set_route(std::size_t index, float gain, bool enabled) noexcept {
   if(!ready_ || index>=count_ || !std::isfinite(gain) || std::fabs(gain)>16.0f) return false;
   gains_[index]=gain; enabled_[index]=enabled; return true;
 }
 bool process(const float* const* inputs, std::size_t count, float* output, std::size_t frames) noexcept {
   if(!ready_ || !inputs || !output || count!=count_ || frames==0 || frames>512) return false;
   const std::size_t samples=frames*channels_;
   for(std::size_t r=0;r<count;++r) {
     if(!inputs[r] || inputs[r]==output) return false;
     for(std::size_t i=0;i<samples;++i) if(!std::isfinite(inputs[r][i])) return false;
   }
   // Pre-attenuation happens before delay lines. We keep the original streams untouched.
   for(std::size_t r=0;r<count;++r) {
     for(std::size_t i=0;i<samples;++i) scratch_[r][i]=enabled_[r]?inputs[r][i]*gains_[r]:0.0f;
     input_ptrs_[r]=scratch_[r].data();
   }
   // The underlying VST3 PDC processor averages over configured active routes.
   return pdc_.process(input_ptrs_.data(), count, output, frames);
 }
 void reset() noexcept {pdc_.reset();}
private:
 std::size_t channels_; Vst3PdcProcessor pdc_; std::size_t count_;
 std::array<float,kPdcMaxRoutes> gains_{};
 std::array<bool,kPdcMaxRoutes> enabled_{};
 std::array<std::array<float,1024>,kPdcMaxRoutes> scratch_{};
 std::array<const float*,kPdcMaxRoutes> input_ptrs_{};
 bool ready_=false;
};
} // namespace mta
