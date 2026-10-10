// Recovery policy for CONTROL THREAD only, never call on audio callback.
#pragma once
#include <cstdint>
#include <limits>
namespace mta {
class Vst3RecoveryPolicy final {
public:
  explicit Vst3RecoveryPolicy(std::uint32_t max_attempts=3) noexcept
    : max_attempts_(max_attempts <= 16 ? max_attempts : 16) {}
  bool may_restart() const noexcept { return attempts_ < max_attempts_; }
  std::uint64_t next_backoff_ms() noexcept {
    if (!may_restart()) return 0;
    const std::uint64_t delay=static_cast<std::uint64_t>(250) << attempts_;
    ++attempts_;
    return delay;
  }
  void stable_session() noexcept { attempts_=0; }
  std::uint32_t attempts() const noexcept { return attempts_; }
private:
  std::uint32_t max_attempts_,attempts_=0;
};
} // namespace mta
