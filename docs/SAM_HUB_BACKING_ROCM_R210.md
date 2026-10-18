# SAM Audio / Hugging Face Hub and backing-vocal ROCm — 0.3.0-r210

## Evidence and limits

The uploaded structured diagnostic archive records the last stem-separation failure at 2026-10-18 03:26:14 UTC with exit code 1 and TypeError followed by CalledProcessError. It does not contain the exception message, stage, selected model or dependency versions. Therefore the exact originating exception on that server cannot be established from this bundle alone.

The official SAM BaseModel loader still requires the removed proxies and resume_download arguments and forwards them to snapshot_download. This known upstream compatibility problem matches the exception type. We reproduced it with the official BaseModel source and installed huggingface_hub 2.2.0, with tensor/weight IO stubbed and no network/model download; the same loader succeeds with the MTA bridge. The report is validation/r210-sam-live-hub-probe.log. This is a loader-contract test, not a real model inference.

Sources:

- https://github.com/facebookresearch/sam-audio/blob/main/sam_audio/model/base.py
- https://github.com/facebookresearch/sam-audio/pull/97
- https://github.com/nomadkaraoke/python-audio-separator/blob/main/audio_separator/separator/architectures/mdx_separator.py
- https://onnxruntime.ai/docs/execution-providers/ROCm-ExecutionProvider.html

## Changes

SAM loading now scopes a compatibility bridge to the worker's model-loading phase: supply missing legacy defaults, omit only removed snapshot options when its signature no longer accepts them, and restore all bindings on success or failure. Authentication, cache options, revisions, strict state loading and weights_only remain intact. No Hub downgrade, third-party file rewrite or alternative checkpoint is applied. The installer now exercises the actual installed SAM/Hub loader using an empty local probe model, in addition to codec and GPU checks, before marking the environment ready. Native packages include the bridge beside the standalone worker.

SAM worker failures emit fixed stage codes (imports, model load, processor load, audio processing, inference, audio save). Structured diagnostics retain these categories without arbitrary traceback, prompts or credentials. The known Hub TypeError and ROCm backing-vocal failures have dedicated safe categories. Original server journal exceptions remain available under existing redaction rules. Existing historical bundles cannot be retroactively enriched.

The default backing-vocal checkpoint is an ONNX MDX model, while the server installer installs CPU ONNX Runtime. A ROCm PyTorch build alone does not accelerate that ONNX forward pass. For a loaded ONNX backing-vocal model on an available ROCm device, MTA now converts that same checkpoint with audio-separator's existing onnx2torch dependency and runs its forward pass on PyTorch's cuda device API for ROCm. The original segment dimensions, model selection and output labeling are retained. This is shared by native/local and queued server adapters. CPU, NVIDIA and checkpoint-based RoFormer routes retain their existing behavior. Conversion failures stop explicitly instead of silently continuing on CPU.

The forward pass runs in the existing job subprocess and profiler scope. No changes weaken cgroup isolation, artifact checks, accounting attribution or GPU billing validation; device configuration is not proof of verified GPU consumption. Failed/invalid measurements remain non-billable.

## Validation

87 targeted tests passed, including simulated Hub 0.x and modern contracts, restoration after errors, preservation of auth/cache/revision parameters, actual worker CLI/prompt/anchors/output WAV with model doubles, ROCm forward dispatch using the selected ONNX path, explicit conversion failures, installer checks, artifact security and multi-singer flows. Ruff checks passed across app, native and tests. The additional environment/integration regression passed 38 tests. Final full regression: 3,839 passed, zero failures, 5 skipped (optional Steinberg SDK or real Win32 APIs), 10 deselected (AF_UNIX host-agent sockets unavailable under runner policy). Coverage: 76.51%, above the required 70%. Initial runner dependency failures were resolved by installing its missing pytest-asyncio, cmake and WeasyPrint; the static RoFormer load assertion now follows the shared loader while preserving its actionable-error checks.

Final full-suite results are recorded in validation/r210-sam-hub-backing-full.log and its JUnit XML.

The environment does not provide ROCm hardware, installed SAM weights or audio-separator ML models. Real SAM separation, ONNX conversion for the installed checkpoint, audio quality and measured GPU consumption must still be verified on the updated server. Do not regard this package as live server certification.

## Installation and verification

Install the newly built server package and restart the service through the normal update procedure. The runtime SAM bridge and backing-vocal routing apply to the existing isolated Python environments; reinstalling all engines solely for these code changes is unnecessary. The installer preflight is additionally effective on future engine setup runs. SAM still needs authorized model access for the service account.

Run a short SAM separation and a backing-vocal separation with the same selected model. Verify output playback and reopening, GPU activity and the AI queue consumption. For the MDX ROCm route the journal reports `Backing-vocal MDX inference configured for PyTorch ROCm`. If SAM still fails, obtain a new diagnostic bundle to distinguish the newly recorded failure stage; use the corresponding service journal traceback to establish the full original cause. Do not enable billing for an unverified measurement.

## Cumulative scope

VERSION remains 0.3.0 and REVISION remains 210. Every file in MTA-0.3.0-r210-decimal-bpm-metronome-cumulative.zip is retained, including admin erasure and backup/restore, queue ownership/accounting, decimal BPM, metronome regeneration and R shortcut work. No Git commit, push, tag, release or deployed-server operation is performed.
