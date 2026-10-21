// OddVoices adapter, Apache-2.0. Only managed, hash-verified banks may enter here.
#include "render_dsp.h"
#include "../third_party/oddvoices/cpp/src/liboddvoices.hpp"
#include "../third_party/oddvoices/cpp/src/g2p.hpp"
#include <cmath>
#include <algorithm>
#include <memory>
#include <sstream>

namespace {
struct Vocal {
    oddvoices::Voice voice;
    std::unique_ptr<oddvoices::g2p::G2P> dictionary;
};
}
extern "C" {
MTA_DSP_API unsigned mta_vocal_abi() noexcept { return 1; }
MTA_DSP_API void* mta_vocal_open(const char* bank,const char* dictionary) noexcept {
    try {
        if (!bank || !dictionary) return nullptr;
        auto v=std::make_unique<Vocal>();
        v->voice.initFromFile(bank);
        if (!v->voice.hasInitFinished()) return nullptr;
        v->dictionary=std::make_unique<oddvoices::g2p::G2P>(dictionary);
        return v.release();
    } catch (...) { return nullptr; }
}
MTA_DSP_API void mta_vocal_close(void* handle) noexcept { delete static_cast<Vocal*>(handle); }
// Render one syllable or vocalise. Caller schedules notes and checks cancellation
// between notes. A bounded maximum avoids uninterruptible full-song C calls.
MTA_DSP_API int mta_vocal_note(void* handle,const char* text,int phonemes,
    double frequency,double duration,unsigned rate,float formant,float speed,
    float* output,unsigned frames) noexcept {
    try {
        if (!handle || !text || !output || !std::isfinite(frequency) || frequency<20 || frequency>5000 ||
            !std::isfinite(duration) || duration<=0 || duration>30 || rate<8000 || rate>96000 ||
            !std::isfinite(formant) || formant<0.5f || formant>2 ||
            !std::isfinite(speed) || speed<0.5f || speed>2 || frames>rate*31u) return -1;
        auto& v=*static_cast<Vocal*>(handle);
        std::vector<std::string> phones;
        if (phonemes) {
            std::istringstream input(text);std::string phone;
            while (input>>phone) {
                if (v.voice.phonemeToPhonemeIndex(phone)<0 || phones.size()>=128) return -2;
                phones.push_back(phone);
            }
        } else { phones=v.dictionary->pronounce(text); }
        if (phones.empty()) return -2;
        unsigned vowels=0;
        for (const auto& p:phones)
            if (std::find(oddvoices::g2p::k_vowels.begin(),oddvoices::g2p::k_vowels.end(),p)!=oddvoices::g2p::k_vowels.end()) ++vowels;
        if (vowels!=1) return -5;
        auto queue=v.voice.convertPhonemesToSegmentIndices(phones);
        if (queue.empty()) return -2;
        oddvoices::Synth synth(static_cast<float>(rate),&v.voice,queue.data(),static_cast<int>(queue.size()),0,static_cast<int>(queue.size()));
        if (synth.isErrored()) return -3;
        synth.setFrequencyImmediate(static_cast<float>(frequency));
        synth.setFormantShift(formant);synth.setPhonemeSpeed(speed);
        synth.noteOn(static_cast<float>(duration));
        for (unsigned i=0;i<frames;++i) output[i]=synth.process()/32768.0f;
        return 0;
    } catch (...) { return -4; }
}
}
