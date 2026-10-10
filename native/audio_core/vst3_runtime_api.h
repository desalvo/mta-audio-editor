/* MTA experimental VST3 native runtime ABI v2.
 * Lifecycle functions: control thread only, with audio callback quiescent.
 * process() and callback_stats(): audio thread only, single caller.
 * NEVER free a handle or stop the runtime while process() is executing.
 * This does NOT activate native_host_ready and does NOT load VST3 plugins.
 */
#ifndef MTA_VST3_RUNTIME_API_H
#define MTA_VST3_RUNTIME_API_H
#include <stdint.h>
#if defined(_WIN32)
# if defined(MTA_VST3_RUNTIME_BUILD)
#  define MTA_RT_PUBLIC __declspec(dllexport)
# else
#  define MTA_RT_PUBLIC __declspec(dllimport)
# endif
#else
# define MTA_RT_PUBLIC __attribute__((visibility("default")))
#endif
#ifdef __cplusplus
# define MTA_RT_NOEXCEPT noexcept
extern "C" {
#else
# define MTA_RT_NOEXCEPT
#endif
typedef int (*mta_vst3_process_fn)(const float*,float*,uint32_t,uint32_t,void*);
typedef struct MtaVst3RuntimeStatsV1 {
  uint64_t idle_polls, iterations, failures, completions;
} MtaVst3RuntimeStatsV1;
typedef struct MtaVst3PlayoutStatsV2 {
  uint64_t submitted, dropped, processed, bypassed, late, poll_budget_exhausted;
} MtaVst3PlayoutStatsV2;
typedef struct MtaVst3ConfigV2 {
  uint32_t frames, channels, sample_rate, queue_blocks, lookahead_blocks;
} MtaVst3ConfigV2;
MTA_RT_PUBLIC void* mta_vst3_rt_create(uint32_t,uint32_t,uint32_t,uint32_t,uint32_t) MTA_RT_NOEXCEPT;
MTA_RT_PUBLIC int mta_vst3_rt_start(void*,mta_vst3_process_fn,void*) MTA_RT_NOEXCEPT;
MTA_RT_PUBLIC int mta_vst3_rt_process(void*,const float*,float*,uint32_t,uint32_t) MTA_RT_NOEXCEPT;
MTA_RT_PUBLIC int mta_vst3_rt_state(const void*) MTA_RT_NOEXCEPT;
MTA_RT_PUBLIC void mta_vst3_rt_stop(void*) MTA_RT_NOEXCEPT;
MTA_RT_PUBLIC void mta_vst3_rt_destroy(void*) MTA_RT_NOEXCEPT;
MTA_RT_PUBLIC uint32_t mta_vst3_rt_abi_version(void) MTA_RT_NOEXCEPT;
MTA_RT_PUBLIC int mta_vst3_rt_stopped_stats(const void*,MtaVst3RuntimeStatsV1*) MTA_RT_NOEXCEPT;
MTA_RT_PUBLIC int mta_vst3_rt_ready(void) MTA_RT_NOEXCEPT;
MTA_RT_PUBLIC int mta_vst3_rt_callback_stats(const void*,MtaVst3PlayoutStatsV2*) MTA_RT_NOEXCEPT;
MTA_RT_PUBLIC int mta_vst3_rt_configuration(const void*,MtaVst3ConfigV2*) MTA_RT_NOEXCEPT;
#ifdef __cplusplus
}
#endif
#endif
