# ROCm EL10 — AMD rocminfo vs EPEL (0.3.0-r208)

The native ROCm bootstrap now resolves rocminfo from the configured AMD EL10 ROCm repository, pins the vendor NEVRA, and prevents the conflicting EPEL rocminfo from participating in that DNF transaction. It does **not** use `--allowerasing`, `--skip-broken`, or unsigned package downloads. EPEL remains available for other dependencies.

Observed issue: AMD ROCm 7.2.4 `rocm-hip-runtime` requires `rocminfo = 1.0.0.70204-93.el10`, while EPEL offers `rocminfo-7.1.0-3.el10_2`.

For machines where AMD's `rocminfo` is not available, installation fails with a diagnostic instead of accepting EPEL's incompatible build. Kernel drivers are not installed.

Local validation: bash syntax and selected regression tests. Live EL10 transaction, runtime/GPU and ACE-Step smoke tests remain outstanding.
