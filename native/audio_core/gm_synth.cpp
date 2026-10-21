// Portable GM backend. TinySoundFont is vendored unchanged under MIT.
#include "render_dsp.h"
#include <cmath>
#include <cstring>
#include <mutex>
#include <memory>
#include <string>
#include <unordered_map>
#define TSF_IMPLEMENTATION
#define TSF_NO_STDIO
#include "../third_party/tinysoundfont/tsf.h"

namespace {
std::mutex fonts_mutex;
struct Font { tsf* data; unsigned references; };
std::unordered_map<std::string, Font> fonts;
struct Synth { tsf* data; std::string identity; unsigned bank_msb[16]{}; unsigned bank_lsb[16]{}; };
}
extern "C" {
MTA_DSP_API unsigned mta_gm_abi() noexcept { return 1; }
MTA_DSP_API void* mta_gm_create(const void* bytes, size_t size, const char* identity,
                               unsigned rate, unsigned voices) noexcept {
    try {
        if (!bytes || !identity || std::strlen(identity)!=64 || size<12 || size>1024ULL*1024*1024 ||
            rate<8000 || rate>192000 || voices<32 || voices>1024) return nullptr;
        std::lock_guard<std::mutex> lock(fonts_mutex);
        auto found=fonts.find(identity);
        if (found==fonts.end()) {
            std::unique_ptr<tsf,decltype(&tsf_close)> font(tsf_load_memory(bytes,static_cast<int>(size)),tsf_close);
            if (!font) return nullptr;
            found=fonts.emplace(identity,Font{font.get(),0}).first;
            font.release();
        }
        tsf* instance=tsf_copy(found->second.data);
        if (!instance) { if (!found->second.references) { tsf_close(found->second.data);fonts.erase(found); } return nullptr; }
        tsf_set_output(instance,TSF_STEREO_INTERLEAVED,static_cast<int>(rate),0);
        if (!tsf_set_max_voices(instance,static_cast<int>(voices))) {
            tsf_close(instance);
            if (!found->second.references) {tsf_close(found->second.data);fonts.erase(found);}
            return nullptr;
        }
        try {
            auto* result=new Synth{instance,identity};
            ++found->second.references;
            return result;
        } catch (...) {
            tsf_close(instance);
            if (!found->second.references) {tsf_close(found->second.data);fonts.erase(found);}
            throw;
        }
    } catch (...) { return nullptr; }
}
MTA_DSP_API void mta_gm_close(void* handle) noexcept {
    if (!handle) return;
    auto* synth=static_cast<Synth*>(handle);
    std::lock_guard<std::mutex> lock(fonts_mutex);
    tsf_close(synth->data);
    auto found=fonts.find(synth->identity);
    if (found!=fonts.end() && !--found->second.references) {tsf_close(found->second.data);fonts.erase(found);}
    delete synth;
}
MTA_DSP_API int mta_gm_configure(void* handle,float gain,unsigned voices) noexcept {
    if (!handle || !std::isfinite(gain) || gain<0 || gain>5 || voices<32 || voices>1024) return -1;
    auto* synth=static_cast<Synth*>(handle);
    tsf_set_volume(synth->data,gain);
    return tsf_set_max_voices(synth->data,static_cast<int>(voices))?0:-1;
}
MTA_DSP_API int mta_gm_program(void* handle,unsigned channel,unsigned bank,unsigned program) noexcept {
    if (!handle || channel>15 || bank>16383 || program>127) return -1;
    auto* synth=static_cast<Synth*>(handle);
    if (!tsf_channel_set_bank_preset(synth->data,static_cast<int>(channel),
        static_cast<int>(bank),static_cast<int>(program))) return -1;
    // Bank select is 14-bit MSB/LSB and only takes effect on program change.
    synth->bank_msb[channel]=bank>>7; synth->bank_lsb[channel]=bank&127;
    return 0;
}
MTA_DSP_API int mta_gm_event(void* handle,unsigned status,unsigned a,unsigned b) noexcept {
    if (!handle || status<128 || status>239 || a>127 || b>127) return -1;
    auto* synth=static_cast<Synth*>(handle);
    tsf* f=synth->data;int channel=status&15;
    switch(status&240) {
    case 128:tsf_channel_note_off(f,channel,a);return 0;
    case 144:if (!b) {tsf_channel_note_off(f,channel,a);return 0;}
             return tsf_channel_note_on(f,channel,a,b/127.0f)?0:-1;
    case 176:
        if (a==0 || a==32) {
            if (a==0) synth->bank_msb[channel]=b; else synth->bank_lsb[channel]=b;
            return tsf_channel_set_bank(f,channel,(synth->bank_msb[channel]<<7)|synth->bank_lsb[channel])?0:-1;
        }
        if (!tsf_channel_midi_control(f,channel,a,b)) return -1;
        // Reset All Controllers does not reset bank/program selection in GM.
        if (a==121) return tsf_channel_set_bank(f,channel,(synth->bank_msb[channel]<<7)|synth->bank_lsb[channel])?0:-1;
        return 0;
    case 192:return tsf_channel_set_presetnumber(f,channel,a,channel==9)?0:-1;
    case 224:return tsf_channel_set_pitchwheel(f,channel,a+(b<<7))?0:-1;
    // Pressure is intentionally unsupported: use FluidSynth or a VSTi.
    default:return -2;
    }
}
MTA_DSP_API int mta_gm_render(void* handle,float* output,unsigned frames) noexcept {
    if (!handle || !output || !frames || frames>32768) return -1;
    tsf_render_float(static_cast<Synth*>(handle)->data,output,static_cast<int>(frames),0);
    return 0;
}
MTA_DSP_API void mta_gm_reset(void* handle) noexcept {
    if (handle) {
        auto* synth=static_cast<Synth*>(handle);tsf_reset(synth->data);
        for (unsigned c=0;c<16;++c) synth->bank_msb[c]=synth->bank_lsb[c]=0;
    }
}
}
