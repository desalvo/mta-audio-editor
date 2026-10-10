// Experimental native ABI to exercise the VST3 playout transport from a host.
// create/start/stop/destroy are CONTROL THREAD ONLY. process is callback-only.
// No plugin loading, Python, lock, heap allocation or IPC occurs in process.
#define MTA_VST3_RUNTIME_BUILD
#include "vst3_runtime_api.h"
#include "vst3_worker_runtime.hpp"
#include <cstddef>
#include <cstdint>
#include <new>
#define MTA_VST3_API extern "C"
namespace {
using ProcessFn = mta_vst3_process_fn;
struct Handle {
  mta::Vst3WorkerRuntime runtime;
  const std::size_t frames;
  const std::size_t channels;
  explicit Handle(mta::WorkerRuntimeConfig config) : runtime(config), frames(config.quantum.frames), channels(config.quantum.channels) {}
};
}
MTA_VST3_API void* mta_vst3_rt_create(std::uint32_t frames, std::uint32_t channels,
                                      std::uint32_t rate, std::uint32_t queue_blocks,
                                      std::uint32_t lookahead_blocks) noexcept {
  mta::WorkerRuntimeConfig config;
  if (frames == 0 || frames > 512 || channels < 1 || channels > 2) return nullptr;
  config.quantum = {static_cast<std::uint16_t>(frames), static_cast<std::uint8_t>(channels), rate};
  config.queue_blocks = queue_blocks;
  config.lookahead_blocks = lookahead_blocks;
  if (!config.valid()) return nullptr;
  auto* handle = new (std::nothrow) Handle(config);
  if (!handle) return nullptr;
  if (!handle->runtime.valid()) { delete handle; return nullptr; }
  return handle;
}
MTA_VST3_API int mta_vst3_rt_start(void* ptr, ProcessFn processor, void* user) noexcept {
  if (!ptr || !processor) return -1;
  auto* h = static_cast<Handle*>(ptr);
  try {
    return h->runtime.start([processor, user](const float* in, float* out, std::size_t f, std::size_t c) {
      return processor(in, out, static_cast<std::uint32_t>(f), static_cast<std::uint32_t>(c), user) == 0;
    }) ? 0 : -2;
  } catch (...) { return -3; }
}
MTA_VST3_API int mta_vst3_rt_process(void* ptr, const float* in, float* out,
                                     std::uint32_t frames, std::uint32_t channels) noexcept {
  if (!ptr || !in || !out) return -1;
  auto* h = static_cast<Handle*>(ptr);
  if (frames != h->frames || channels != h->channels) {
    // output capacity is owned by the caller (frames * channels). It cannot
    // be assumed to hold the negotiated quantum when shapes differ.
    if (frames <= mta::kMaxBlockFrames && channels >= 1 && channels <= 2)
      for (std::size_t i = 0; i < std::size_t(frames) * channels; ++i) out[i] = 0.0f;
    return -2;
  }
  // A failed/stopped runtime may still hold stale response blocks. The host
  // must create a new runtime and must not attempt to playout those blocks.
  if (h->runtime.state() != mta::WorkerRuntimeState::running) {
    for (std::size_t i = 0; i < h->frames * h->channels; ++i) out[i] = 0.0f;
    return -4;
  }
  // This is deliberately non-blocking. No processor callback or IPC is invoked here.
  return h->runtime.bridge().callback(in, out, frames, channels) ? 0 : -3;
}
MTA_VST3_API int mta_vst3_rt_state(const void* ptr) noexcept {
  if (!ptr) return -1;
  return static_cast<int>(static_cast<const Handle*>(ptr)->runtime.state());
}
MTA_VST3_API void mta_vst3_rt_stop(void* ptr) noexcept {
  if (ptr) static_cast<Handle*>(ptr)->runtime.stop();
}
MTA_VST3_API void mta_vst3_rt_destroy(void* ptr) noexcept {
  delete static_cast<Handle*>(ptr);
}
// The ABI version is independent of the plugin protocol. Query this before using
// structs exported by a potentially newer native library.
MTA_VST3_API std::uint32_t mta_vst3_rt_abi_version() noexcept { return 2; }
// Control thread only, after stop(). Never read mutable worker counters live.
// Caller must supply a valid object sized for ABI v1.
MTA_VST3_API int mta_vst3_rt_stopped_stats(const void* ptr,
                                           MtaVst3RuntimeStatsV1* result) noexcept {
  if (!ptr || !result) return -1;
  const auto* h = static_cast<const Handle*>(ptr);
  if (h->runtime.state() != mta::WorkerRuntimeState::stopped) return -2;
  const auto snap = h->runtime.stopped_stats();
  *result = {snap.idle_polls, snap.iterations, snap.failures, snap.completions};
  return 0;
}
MTA_VST3_API int mta_vst3_rt_ready() noexcept { return 0; }

// ABI v2: read only on the AUDIO CALLBACK THREAD, after processing has started.
// Never poll this from the UI/control thread while callback() may write counters.
MTA_VST3_API int mta_vst3_rt_callback_stats(const void* ptr,
                                            MtaVst3PlayoutStatsV2* result) noexcept {
  if (!ptr || !result) return -1;
  auto* h = const_cast<Handle*>(static_cast<const Handle*>(ptr));
  const auto stats = h->runtime.bridge().stats();
  *result = {stats.submitted, stats.dropped, stats.processed, stats.bypassed,
             stats.late, stats.poll_budget_exhausted};
  return 0;
}
// Only on the control thread, with callback quiescent. Return actual negotiated quantum.
MTA_VST3_API int mta_vst3_rt_configuration(const void* ptr,
                                           MtaVst3ConfigV2* result) noexcept {
  if (!ptr || !result) return -1;
  const auto& config = static_cast<const Handle*>(ptr)->runtime.configuration();
  *result = {static_cast<std::uint32_t>(config.quantum.frames),
             static_cast<std::uint32_t>(config.quantum.channels),
             config.quantum.rate, static_cast<std::uint32_t>(config.queue_blocks),
             static_cast<std::uint32_t>(config.lookahead_blocks)};
  return 0;
}
