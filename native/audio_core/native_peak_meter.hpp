// Native stereo or mono peak/RMS meter. No allocation or I/O in process().
#pragma once
#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>
namespace mta::audio {
class NativePeakMeter final {
public:
    void reset() noexcept { peak_[0]=peak_[1]=rms_[0]=rms_[1]=0.f; }
    bool process(const float* interleaved, std::size_t frames, std::size_t channels) noexcept {
        if (!interleaved || frames==0 || frames>8192 || (channels!=1 && channels!=2)) return false;
        double power[2]={0.,0.}; float peak[2]={0.f,0.f};
        for(std::size_t i=0;i<frames;++i) for(std::size_t c=0;c<channels;++c) {
            const float sample=interleaved[i*channels+c];
            if(!std::isfinite(sample)) return false;
            peak[c]=std::max(peak[c],std::abs(sample));
            power[c]+=double(sample)*sample;
        }
        for(std::size_t c=0;c<channels;++c) {peak_[c]=peak[c];rms_[c]=float(std::sqrt(power[c]/frames));}
        if(channels==1){peak_[1]=peak_[0];rms_[1]=rms_[0];}
        return true;
    }
    float peak(std::size_t channel) const noexcept {return channel<2?peak_[channel]:0.f;}
    float rms(std::size_t channel) const noexcept {return channel<2?rms_[channel]:0.f;}
private:
    float peak_[2]={0.f,0.f};float rms_[2]={0.f,0.f};
};
}
