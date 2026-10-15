# CI r208 – unified worker executable permission

The quality job (run 38682990623) finished in 116.62 seconds with 3,127 passed, 4 skipped and one failure. The only failure was `test_unified_worker_registry_opt_in`: the `ai_unified_adapter.py` script was archived with POSIX mode `100644` despite the `#!/usr/bin/env python3` shebang, so the worker registry's security requirement `os.access(path, os.X_OK)` returned false.

Fixed: `app/ai_unified_adapter.py` is shipped with POSIX mode `100755` (Git index must preserve this executable bit). A regression checks both the executable mode and real opt-in worker resolution.

Do not weaken or remove the executable path verification in `ai_worker_registry.py`. Check after extracting or committing that `git ls-files --stage app/ai_unified_adapter.py` displays `100755`.
