// Prepared, immutable timeline ABI. Creation/destruction run on the control thread.
#pragma once
#include "render_dsp.h"
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
typedef struct mta_timeline_plan mta_timeline_plan;
typedef struct {uint64_t start,source,frames;uint32_t route;} mta_timeline_clip;
typedef struct {uint64_t source;uint32_t clip,route,offset,frames;} mta_timeline_slice;
MTA_DSP_API unsigned mta_timeline_abi(void) MTA_DSP_NOEXCEPT;
// Copies and validates <=100000 clips, <=64 routes; same-route overlap rejected.
// Source coordinates and project coordinates must fit signed 64-bit frame indices.
MTA_DSP_API mta_timeline_plan* mta_timeline_create(const mta_timeline_clip*,size_t) MTA_DSP_NOEXCEPT;
MTA_DSP_API void mta_timeline_destroy(mta_timeline_plan*) MTA_DSP_NOEXCEPT;
// Absolute position supports seek/replay without mutable cursors. <=4096 frames.
// Returns slice count, -1 invalid, -2 insufficient capacity. Failure leaves output
// unchanged. No allocation, file IO, locks or reference-count mutation in query.
MTA_DSP_API int mta_timeline_query(const mta_timeline_plan*,uint64_t,uint32_t,
    mta_timeline_slice*,size_t) MTA_DSP_NOEXCEPT;
#ifdef __cplusplus
}
#endif
