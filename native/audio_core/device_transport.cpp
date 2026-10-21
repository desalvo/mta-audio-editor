#define MINIAUDIO_IMPLEMENTATION
#define MA_NO_ENCODING
#define MA_NO_RESOURCE_MANAGER
#define MA_NO_NODE_GRAPH
#define MA_NO_ENGINE
#include "../third_party/miniaudio/miniaudio.h"
#include "device_transport.h"
#include <array>
#include <atomic>
#include <thread>
#include <chrono>
#include <cmath>
#include <cstring>
#include <algorithm>
#include <string>
static_assert(std::atomic<uint64_t>::is_always_lock_free);
static_assert(std::atomic<float>::is_always_lock_free);
struct mta_capture;
namespace {void capture_consume(mta_capture*,const void*,uint32_t) noexcept;void capture_overflow(mta_capture*) noexcept;}
struct mta_transport {
    static constexpr uint64_t capacity=65536;
    ma_context context{};ma_device device{};ma_decoder decoder{};
    bool has_context=false,has_device=false,has_decoder=false,physical=false,external=false,external_output=false;
    uint32_t output_channels=2;std::array<float,128> output_matrix{};
    mta_capture* capture=nullptr;std::atomic<bool> recording{false};
    uint64_t total=0;uint32_t rate=0;
    std::array<float,capacity*2> ring{};
    std::atomic<uint64_t> read{0},write{0},position{0},underruns{0};
    std::atomic<bool> quit{false},eof{false},playing{false},ended{false},failed{false};
    std::atomic<float> gain{1},left{0},right{0};std::thread producer;
};
namespace {
void produce(mta_transport* t) noexcept {
    std::array<float,4096*2> pcm{};
    while(!t->quit.load(std::memory_order_acquire)){
        const auto w=t->write.load(std::memory_order_relaxed),r=t->read.load(std::memory_order_acquire);
        const auto space=mta_transport::capacity-(w-r);
        if(!space){std::this_thread::sleep_for(std::chrono::milliseconds(1));continue;}
        ma_uint64 got=0;const auto want=std::min<uint64_t>(4096,space);
        const auto result=ma_decoder_read_pcm_frames(&t->decoder,pcm.data(),want,&got);
        if(result!=MA_SUCCESS&&result!=MA_AT_END){t->failed.store(true);t->eof.store(true);return;}
        if(!got){t->eof.store(true,std::memory_order_release);return;}
        for(size_t i=0;i<got*2;++i)if(!std::isfinite(pcm[i])){t->failed.store(true);t->eof.store(true);return;}
        for(uint64_t i=0;i<got;++i){const auto at=((w+i)&(mta_transport::capacity-1))*2;t->ring[at]=pcm[i*2];t->ring[at+1]=pcm[i*2+1];}
        t->write.store(w+got,std::memory_order_release);
    }
}
void notification(const ma_device_notification* n) noexcept {
    auto* t=static_cast<mta_transport*>(n->pDevice->pUserData);
    if(n->type==ma_device_notification_type_stopped&&t->playing.exchange(false)){t->failed.store(true);}
}
void consume(mta_transport* t,float* out,uint32_t frames,uint32_t channels) noexcept {
    std::memset(out,0,static_cast<size_t>(frames)*channels*sizeof(float));
    if(!t->playing.load(std::memory_order_acquire)||t->failed.load())return;
    const auto r=t->read.load(std::memory_order_relaxed),w=t->write.load(std::memory_order_acquire);
    const auto n=(std::min<uint64_t>)(frames,w-r);const float gain=t->gain.load(std::memory_order_relaxed);float left=0,right=0;
    for(uint64_t i=0;i<n;++i){const auto at=((r+i)&(mta_transport::capacity-1))*2;
        const float l=std::clamp(t->ring[at]*gain,-1.0f,1.0f),rvalue=std::clamp(t->ring[at+1]*gain,-1.0f,1.0f);
        if(t->external_output){for(uint32_t channel=0;channel<channels;++channel)
            out[i*channels+channel]=std::clamp(l*t->output_matrix[channel*2]+rvalue*t->output_matrix[channel*2+1],-1.0f,1.0f);
        }else{out[i*2]=l;out[i*2+1]=rvalue;}
        left=(std::max)(left,std::fabs(l));right=(std::max)(right,std::fabs(rvalue));}
    t->read.store(r+n,std::memory_order_release);t->position.fetch_add(n,std::memory_order_relaxed);
    t->left.store(left,std::memory_order_relaxed);t->right.store(right,std::memory_order_relaxed);
    if(n<frames){if(t->eof.load(std::memory_order_acquire)&&r+n==t->write.load(std::memory_order_acquire))t->ended.store(true);else t->underruns.fetch_add(1,std::memory_order_relaxed);}
}
void callback(ma_device* device,void* output,const void*,ma_uint32 frames) noexcept {
    consume(static_cast<mta_transport*>(device->pUserData),static_cast<float*>(output),frames,2);
}
// PortAudio calls this C++ function directly: no CFFI/Python callback or GIL.
int portaudio_output(const void* input,void* output,unsigned long frames,const void*,unsigned long flags,void* user) noexcept {
    auto* t=static_cast<mta_transport*>(user);
    if(!t||!output||!frames||frames>32768)return 2;
    if(t->capture&&t->recording.load(std::memory_order_acquire)){if(flags&2)capture_overflow(t->capture);else capture_consume(t->capture,input,static_cast<uint32_t>(frames));}
    if(flags&4)t->underruns.fetch_add(1,std::memory_order_relaxed);
    consume(t,static_cast<float*>(output),static_cast<uint32_t>(frames),t->output_channels);
    return t->failed.load()?2:0;
}

void fill(mta_transport* t){
    t->quit.store(false);t->producer=std::thread(produce,t);
    for(unsigned i=0;i<300&&t->write.load()<4096&&!t->eof.load();++i)std::this_thread::sleep_for(std::chrono::milliseconds(1));
}
}
unsigned mta_transport_abi(void) noexcept{return 1;}
mta_transport* mta_transport_open(const char* path,unsigned test_null) noexcept {
    if(!path||!*path||test_null>1)return nullptr;
    mta_transport* t=nullptr;
    try{
        t=new mta_transport;auto dc=ma_decoder_config_init(ma_format_f32,2,0);
        ma_result result;
#ifdef _WIN32
        const int n=MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,path,-1,nullptr,0);
        if(!n){delete t;return nullptr;}std::wstring wide(static_cast<size_t>(n),L'\0');
        MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,path,-1,wide.data(),n);
        result=ma_decoder_init_file_w(wide.c_str(),&dc,&t->decoder);
#else
        result=ma_decoder_init_file(path,&dc,&t->decoder);
#endif
        if(result!=MA_SUCCESS){delete t;return nullptr;}t->has_decoder=true;t->rate=t->decoder.outputSampleRate;
        ma_uint64 total=0;if(ma_decoder_get_length_in_pcm_frames(&t->decoder,&total)!=MA_SUCCESS||!total||!t->rate){mta_transport_close(t);return nullptr;}t->total=total;
        const ma_backend null_backend=ma_backend_null;
        result=ma_context_init(test_null?&null_backend:nullptr,test_null?1:0,nullptr,&t->context);
        if(result!=MA_SUCCESS){mta_transport_close(t);return nullptr;}t->has_context=true;t->physical=t->context.backend!=ma_backend_null;
        if(!test_null&&!t->physical){mta_transport_close(t);return nullptr;}
        auto cfg=ma_device_config_init(ma_device_type_playback);cfg.playback.format=ma_format_f32;cfg.playback.channels=2;
        cfg.sampleRate=t->rate;cfg.periodSizeInFrames=512;cfg.dataCallback=callback;cfg.notificationCallback=notification;cfg.pUserData=t;
        if(ma_device_init(&t->context,&cfg,&t->device)!=MA_SUCCESS){mta_transport_close(t);return nullptr;}t->has_device=true;
        fill(t);return t;
    }catch(...){mta_transport_close(t);return nullptr;}
}
int mta_transport_play(mta_transport* t) noexcept {
    if(!t||t->failed.load()||t->ended.load())return -1;
    if(t->playing.exchange(true))return 0;
    if(!t->external_output&&ma_device_start(&t->device)!=MA_SUCCESS){t->playing.store(false);return -2;}return 0;
}
int mta_transport_pause(mta_transport* t) noexcept {
    if(!t)return -1;
    t->playing.store(false);
    if(!t->external_output&&ma_device_stop(&t->device)!=MA_SUCCESS)return -2;
    return 0;
}
int mta_transport_seek(mta_transport* t,uint64_t frame) noexcept {
    if(!t||frame>t->total)return -1;
    try{
        const bool resume=t->playing.load();if(mta_transport_pause(t))return -2;
        t->quit.store(true);if(t->producer.joinable())t->producer.join();
        if(!t->external&&ma_decoder_seek_to_pcm_frame(&t->decoder,frame)!=MA_SUCCESS){t->failed.store(true);return -3;}
        t->read.store(0);t->write.store(0);t->position.store(frame);t->ended.store(false);t->eof.store(false);t->failed.store(false);
        t->left.store(0);t->right.store(0);if(!t->external)fill(t);
        return resume?mta_transport_play(t):0;
    }catch(...){t->failed.store(true);return -4;}
}
int mta_transport_gain(mta_transport* t,float gain) noexcept {if(!t||!std::isfinite(gain)||gain<0||gain>128)return -1;t->gain.store(gain);return 0;}
int mta_transport_status(const mta_transport* t,mta_transport_state* out) noexcept {
    if(!t||!out)return -1;
    *out={t->position.load(),t->total,t->underruns.load(),t->rate,t->playing.load()?1u:0u,t->ended.load()?1u:0u,t->failed.load()?1u:0u,t->physical?1u:0u,t->left.load(),t->right.load()};return 0;
}
void mta_transport_close(mta_transport* t) noexcept {
    if(!t)return;
    if(t->has_device){t->playing.store(false);ma_device_uninit(&t->device);}
    t->quit.store(true);if(t->producer.joinable())t->producer.join();
    if(t->has_decoder)ma_decoder_uninit(&t->decoder);
    if(t->has_context)ma_context_uninit(&t->context);
    delete t;
}

mta_transport* mta_transport_open_stream(uint32_t rate,uint64_t total,unsigned test_null) noexcept {
    if((rate!=44100&&rate!=48000&&rate!=96000)||!total||total>INT64_MAX||test_null>1)return nullptr;
    mta_transport* t=nullptr;
    try {
        t=new mta_transport;t->external=true;t->rate=rate;t->total=total;
        const ma_backend null_backend=ma_backend_null;
        if(ma_context_init(test_null?&null_backend:nullptr,test_null?1:0,nullptr,&t->context)!=MA_SUCCESS){delete t;return nullptr;}
        t->has_context=true;t->physical=t->context.backend!=ma_backend_null;
        if(!test_null&&!t->physical){mta_transport_close(t);return nullptr;}
        auto cfg=ma_device_config_init(ma_device_type_playback);cfg.playback.format=ma_format_f32;cfg.playback.channels=2;
        cfg.sampleRate=rate;cfg.periodSizeInFrames=512;cfg.dataCallback=callback;cfg.notificationCallback=notification;cfg.pUserData=t;
        if(ma_device_init(&t->context,&cfg,&t->device)!=MA_SUCCESS){mta_transport_close(t);return nullptr;}
        t->has_device=true;return t;
    }catch(...){mta_transport_close(t);return nullptr;}
}
int mta_transport_push(mta_transport* t,const float* pcm,uint32_t frames) noexcept {
    if(!t||!t->external||!pcm||!frames||frames>4096||t->eof.load()||t->failed.load())return -1;
    for(size_t i=0;i<size_t(frames)*2;++i)if(!std::isfinite(pcm[i]))return -2;
    const auto w=t->write.load(std::memory_order_relaxed),r=t->read.load(std::memory_order_acquire);
    if(frames>mta_transport::capacity-(w-r))return 1;
    for(uint64_t i=0;i<frames;++i){const auto at=((w+i)&(mta_transport::capacity-1))*2;t->ring[at]=pcm[i*2];t->ring[at+1]=pcm[i*2+1];}
    t->write.store(w+frames,std::memory_order_release);return 0;
}
uint64_t mta_transport_buffered(const mta_transport* t) noexcept {
    if(!t)return 0;
    const auto r=t->read.load(std::memory_order_acquire),w=t->write.load(std::memory_order_acquire);return w-r;
}
int mta_transport_finish(mta_transport* t) noexcept {
    if(!t||!t->external)return -1;
    t->eof.store(true,std::memory_order_release);return 0;
}

struct mta_capture {
    ma_context context{};ma_device device{};bool context_ready=false,device_ready=false,external=false;
    uint32_t input_channels=2;std::array<float,128> input_matrix{};
    static constexpr uint64_t capacity=131072;
    std::array<float,capacity*2> ring{};
    std::atomic<uint64_t> read{0},write{0};std::atomic<bool> failed{false};
};
namespace {
void capture_notification(const ma_device_notification* n) noexcept {
    if(n->type==ma_device_notification_type_stopped)static_cast<mta_capture*>(n->pDevice->pUserData)->failed.store(true);
}
void capture_overflow(mta_capture* c) noexcept {c->failed.store(true);}
void capture_consume(mta_capture* c,const void* input,uint32_t count) noexcept {
    const auto w=c->write.load(std::memory_order_relaxed),r=c->read.load(std::memory_order_acquire);
    if(!input || count>mta_capture::capacity-(w-r)){c->failed.store(true);return;}
    const auto* data=static_cast<const float*>(input);const uint32_t channels=c->input_channels;
    for(uint64_t i=0;i<count;i++) {
        const auto at=((w+i)&(mta_capture::capacity-1))*2;
        float left=0,right=0;
        if(c->external){for(uint32_t channel=0;channel<channels;++channel){
            const float value=data[i*channels+channel];if(!std::isfinite(value)){c->failed.store(true);return;}
            left+=value*c->input_matrix[channel];right+=value*c->input_matrix[channels+channel];}
        }else{left=data[i*2];right=data[i*2+1];}
        if(!std::isfinite(left)||!std::isfinite(right)){c->failed.store(true);return;}
        c->ring[at]=left;c->ring[at+1]=right;
    }
    c->write.store(w+count,std::memory_order_release);
}
void capture_callback(ma_device* d,void*,const void* input,ma_uint32 count) noexcept {
    capture_consume(static_cast<mta_capture*>(d->pUserData),input,count);
}
int portaudio_input(const void* input,void*,unsigned long frames,const void*,unsigned long flags,void* user) noexcept {
    auto* c=static_cast<mta_capture*>(user);if(!c||!frames||frames>32768)return 2;
    if(flags&2){c->failed.store(true);return 2;}
    capture_consume(c,input,static_cast<uint32_t>(frames));return c->failed.load()?2:0;
}

}
int mta_capture_devices(char* output,uint32_t capacity) noexcept {
    if(!output || capacity<4)return -1;
    try {
        ma_context context{};auto config=ma_context_config_init();
        if(ma_context_init(nullptr,0,&config,&context)!=MA_SUCCESS)return -1;
        if(context.backend==ma_backend_null){ma_context_uninit(&context);return -1;}
        ma_device_info* inputs=nullptr;ma_uint32 count=0;
        if(ma_context_get_devices(&context,nullptr,nullptr,&inputs,&count)!=MA_SUCCESS){ma_context_uninit(&context);return -1;}
        std::string json="[";
        for(ma_uint32 i=0;i<count;i++) {
            if(i)json+=",";
            json+='"';
            for(const unsigned char* p=reinterpret_cast<const unsigned char*>(inputs[i].name);*p;p++) {
                if(*p=='"'||*p=='\\')json+='\\';
                if(*p>=32)json+=static_cast<char>(*p);
            }
            json+='"';
        }
        json+=']';ma_context_uninit(&context);
        if(json.size()+1>capacity)return -1;
        std::memcpy(output,json.c_str(),json.size()+1);return static_cast<int>(json.size());
    } catch(...){return -1;}
}
mta_capture* mta_capture_open(const char* name,uint32_t rate,unsigned test_null) noexcept {
    if(!name || (rate!=44100 && rate!=48000 && rate!=96000) || test_null>1)return nullptr;
    mta_capture* c=nullptr;
    try {
        c=new mta_capture;auto context=ma_context_config_init();ma_backend backend=ma_backend_null;
        if(ma_context_init(test_null?&backend:nullptr,test_null?1:0,&context,&c->context)!=MA_SUCCESS){delete c;return nullptr;}
        c->context_ready=true;
        if(!test_null && c->context.backend==ma_backend_null){mta_capture_close(c);return nullptr;}
        ma_device_id chosen{};bool found=!*name;
        if(*name) {
            ma_device_info* inputs=nullptr;ma_uint32 count=0;
            if(ma_context_get_devices(&c->context,nullptr,nullptr,&inputs,&count)!=MA_SUCCESS){mta_capture_close(c);return nullptr;}
            int matches=0;for(ma_uint32 i=0;i<count;i++)if(std::strcmp(name,inputs[i].name)==0){chosen=inputs[i].id;matches++;}
            found=matches==1;
        }
        if(!found){mta_capture_close(c);return nullptr;}
        auto config=ma_device_config_init(ma_device_type_capture);
        config.capture.format=ma_format_f32;config.capture.channels=2;config.sampleRate=rate;
        if(*name)config.capture.pDeviceID=&chosen;
        config.dataCallback=capture_callback;config.notificationCallback=capture_notification;config.pUserData=c;
        if(ma_device_init(&c->context,&config,&c->device)!=MA_SUCCESS){mta_capture_close(c);return nullptr;}
        c->device_ready=true;
        if(ma_device_start(&c->device)!=MA_SUCCESS){mta_capture_close(c);return nullptr;}
        return c;
    }catch(...){if(c)mta_capture_close(c);return nullptr;}
}
int mta_capture_read(mta_capture* c,float* output,uint32_t capacity) noexcept {
    if(!c || !output || !capacity || capacity>32768 || c->failed.load())return -1;
    const auto r=c->read.load(std::memory_order_relaxed),w=c->write.load(std::memory_order_acquire);
    const auto count=std::min<uint64_t>(capacity,w-r);
    for(uint64_t i=0;i<count;i++) {
        const auto at=((r+i)&(mta_capture::capacity-1))*2;output[i*2]=c->ring[at];output[i*2+1]=c->ring[at+1];
    }
    c->read.store(r+count,std::memory_order_release);return static_cast<int>(count);
}
void mta_capture_close(mta_capture* c) noexcept {
    if(!c)return;
    if(c->device_ready)ma_device_uninit(&c->device);
    if(c->context_ready)ma_context_uninit(&c->context);
    delete c;
}


mta_transport* mta_transport_open_external(uint32_t rate,uint64_t total,uint32_t channels,const float* matrix) noexcept {
    if((rate!=44100&&rate!=48000&&rate!=96000)||!total||total>INT64_MAX||!channels||channels>64||!matrix)return nullptr;
    for(uint32_t i=0;i<channels*2;++i)if(!std::isfinite(matrix[i])||std::fabs(matrix[i])>4)return nullptr;
    try{auto* t=new mta_transport;t->external=true;t->external_output=true;t->rate=rate;t->total=total;t->output_channels=channels;
        std::copy(matrix,matrix+channels*2,t->output_matrix.begin());return t;
    }catch(...){return nullptr;}
}
void* mta_transport_external_callback(void) noexcept {return reinterpret_cast<void*>(&portaudio_output);}
int mta_transport_external_attached(mta_transport* t) noexcept {if(!t||!t->external_output)return -1;t->physical=true;return 0;}

mta_capture* mta_capture_open_external(uint32_t channels,const float* matrix) noexcept {
    if(!channels||channels>64||!matrix)return nullptr;
    for(uint32_t i=0;i<channels*2;++i)if(!std::isfinite(matrix[i])||std::fabs(matrix[i])>4)return nullptr;
    try{auto* c=new mta_capture;c->external=true;c->input_channels=channels;
        std::copy(matrix,matrix+channels*2,c->input_matrix.begin());return c;
    }catch(...){return nullptr;}
}
void* mta_capture_external_callback(void) noexcept {return reinterpret_cast<void*>(&portaudio_input);}

int mta_transport_capture_attach(mta_transport* t,mta_capture* c) noexcept {
    if(!t||!t->external_output||t->playing.load())return -1;
    t->capture=c;t->recording.store(c!=nullptr,std::memory_order_release);return 0;
}
