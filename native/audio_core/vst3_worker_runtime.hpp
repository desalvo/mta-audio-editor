// r88-r100: Experimental native scheduler for the VST3 bridge.
// Own on a non-audio control thread; never create/start/stop from audio callback.
// The callback calls only Vst3PlayoutBridge::callback().
#pragma once
#include "vst3_worker_pump.hpp"
#include "vst3_rt_contract.hpp"
#include <atomic>
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <exception>
#include <functional>
#include <memory>
#include <new>
#include <thread>
#include <utility>

namespace mta {
// r88: immutable startup parameters; r89: explicit state lifecycle.
struct WorkerRuntimeConfig {
  std::size_t queue_blocks = 16;
  std::size_t lookahead_blocks = 4;
  std::size_t max_idle_spins = 64;
  Vst3Quantum quantum{512, 2, 48000};
  bool valid() const noexcept {
    return quantum.valid() && queue_blocks >= 3 && queue_blocks <= 4096 &&
           lookahead_blocks > 0 && lookahead_blocks < queue_blocks &&
           max_idle_spins >= 1 && max_idle_spins <= 4096;
  }
};
enum class WorkerRuntimeState : std::uint8_t { stopped, running, faulted };
struct WorkerRuntimeStats {
  std::uint64_t idle_polls = 0;
  std::uint64_t iterations = 0;
  std::uint64_t failures = 0;
  std::uint64_t completions = 0;
};

// r90: caller supplied processor is owned by worker thread, which may block on IPC.
// r91: worker creation / join is exclusively control-plane work.
class Vst3WorkerRuntime final {
public:
  using Processor = std::function<bool(const float*, float*, std::size_t, std::size_t)>;
  explicit Vst3WorkerRuntime(WorkerRuntimeConfig config) noexcept
      : config_(config), bridge_(config.queue_blocks, config.lookahead_blocks) {}
  Vst3WorkerRuntime(const Vst3WorkerRuntime&) = delete;
  Vst3WorkerRuntime& operator=(const Vst3WorkerRuntime&) = delete;
  ~Vst3WorkerRuntime() { stop(); }
  bool valid() const noexcept { return config_.valid() && bridge_.valid(); }
  // r92: process callback never sees a function object or IPC handle.
  Vst3PlayoutBridge& bridge() noexcept { return bridge_; }
  WorkerRuntimeState state() const noexcept { return state_.load(std::memory_order_acquire); }
  bool healthy() const noexcept { return state() == WorkerRuntimeState::running && !fault_.failed(); }
  // r93: start only from a quiescent control thread before audio callbacks begin.
  bool start(Processor processor) {
    if (ever_started_) return false; // new runtime required after stop/fault: queues contain old epoch
    if (!valid() || !processor || thread_.joinable() || state() != WorkerRuntimeState::stopped) return false;
    stop_requested_.store(false, std::memory_order_release);
    fault_.recover();
    state_.store(WorkerRuntimeState::running, std::memory_order_release);
    try { thread_ = std::thread([this, fn=std::move(processor)]() mutable { loop(fn); }); }
    catch (...) { state_.store(WorkerRuntimeState::stopped, std::memory_order_release); return false; }
    ever_started_ = true;
    return true;
  }
  // r94: fault never blocks callback; supervisor may inspect healthy().
  // r95: stop joins on control thread; not callable from callback or worker itself.
  void stop() noexcept {
    stop_requested_.store(true, std::memory_order_release);
    if (thread_.joinable()) {
      if (std::this_thread::get_id() == thread_.get_id()) std::terminate();
      thread_.join();
    }
    state_.store(WorkerRuntimeState::stopped, std::memory_order_release);
  }
  // r96: worker snapshots are copied only once stopped (no data race).
  WorkerRuntimeStats stopped_stats() const noexcept { return stats_; }
  // r97: input quantum negotiation occurs before callbacks start.
  const WorkerRuntimeConfig& configuration() const noexcept { return config_; }
private:
  void loop(Processor& process) noexcept {
    Vst3WorkerPump pump(bridge_);
    std::size_t idle = 0;
    try {
      while (!stop_requested_.load(std::memory_order_acquire)) {
        // r98: bound empty-poll CPU use via cooperative yields/sleeps on worker only.
        const bool handled = pump.pump_once(process);
        if (handled) {
          ++stats_.iterations;
          idle = 0;
          const auto s = pump.stats();
          // r99: latch processing faults; callback falls back to dry when output absent.
          if (s.processing_failures) { ++stats_.failures; fault_.fault(); break; }
        } else {
          ++stats_.idle_polls;
          if (++idle >= config_.max_idle_spins) {
            std::this_thread::sleep_for(std::chrono::microseconds(100));
            idle = 0;
          } else std::this_thread::yield();
        }
      }
      stats_.completions = pump.stats().handled;
    } catch (...) { ++stats_.failures; fault_.fault(); }
    // r100: failed worker stays faulted until a control-plane stop and fresh instance.
    if (fault_.failed()) state_.store(WorkerRuntimeState::faulted, std::memory_order_release);
  }
  const WorkerRuntimeConfig config_;
  Vst3PlayoutBridge bridge_;
  WorkerFaultGate fault_;
  std::atomic<bool> stop_requested_{false};
  std::atomic<WorkerRuntimeState> state_{WorkerRuntimeState::stopped};
  std::thread thread_;
  WorkerRuntimeStats stats_{};
  bool ever_started_ = false; // control-thread only
};
inline constexpr bool kNativeWorkerRealtimeEnabled = false;
} // namespace mta
