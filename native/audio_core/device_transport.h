#pragma once
#include "render_dsp.h"
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
typedef struct mta_transport mta_transport;
typedef struct {uint64_t position,total,underruns;uint32_t rate,playing,ended,failed,physical;float peak_left,peak_right;} mta_transport_state;
MTA_DSP_API unsigned mta_transport_abi(void) MTA_DSP_NOEXCEPT;
// Control thread only. test_null=0 never silently falls back to a null device.
MTA_DSP_API mta_transport* mta_transport_open(const char* utf8_path,unsigned test_null) MTA_DSP_NOEXCEPT;
MTA_DSP_API int mta_transport_play(mta_transport*) MTA_DSP_NOEXCEPT;
MTA_DSP_API int mta_transport_pause(mta_transport*) MTA_DSP_NOEXCEPT;
MTA_DSP_API int mta_transport_seek(mta_transport*,uint64_t frame) MTA_DSP_NOEXCEPT;
MTA_DSP_API int mta_transport_gain(mta_transport*,float gain) MTA_DSP_NOEXCEPT;
MTA_DSP_API int mta_transport_status(const mta_transport*,mta_transport_state*) MTA_DSP_NOEXCEPT;
MTA_DSP_API void mta_transport_close(mta_transport*) MTA_DSP_NOEXCEPT;
// Live producer API: control/worker thread only. One producer, one audio callback.
MTA_DSP_API mta_transport* mta_transport_open_stream(uint32_t rate,uint64_t total,unsigned test_null) MTA_DSP_NOEXCEPT;
MTA_DSP_API int mta_transport_push(mta_transport*,const float* stereo,uint32_t frames) MTA_DSP_NOEXCEPT;
MTA_DSP_API uint64_t mta_transport_buffered(const mta_transport*) MTA_DSP_NOEXCEPT;
MTA_DSP_API int mta_transport_finish(mta_transport*) MTA_DSP_NOEXCEPT;
#ifdef __cplusplus
}
#endif
#ifdef __cplusplus
extern "C" {
#endif
typedef struct mta_capture mta_capture;
// Dedicated capture SPSC ring: callback never enters Python or performs file I/O.
MTA_DSP_API int mta_capture_devices(char* json,uint32_t capacity) MTA_DSP_NOEXCEPT;
MTA_DSP_API mta_capture* mta_capture_open(const char* name,uint32_t rate,unsigned test_null) MTA_DSP_NOEXCEPT;
MTA_DSP_API int mta_capture_read(mta_capture*,float* stereo,uint32_t capacity) MTA_DSP_NOEXCEPT;
MTA_DSP_API void mta_capture_close(mta_capture*) MTA_DSP_NOEXCEPT;
#ifdef __cplusplus
}
#endif
