# Backing-vocal ROCm and historical SAM notes — r210

SAM Audio has been retired. Its former Hub bridge, installer and worker are no longer shipped. See [SAM_REMOVAL_R210_IT_EN.md](SAM_REMOVAL_R210_IT_EN.md). The following supported backing-vocal route remains unchanged.

The default backing-vocal checkpoint is an ONNX MDX model, while the server installer installs CPU ONNX Runtime. A ROCm PyTorch build alone does not accelerate that ONNX forward pass. For a loaded ONNX backing-vocal model on an available ROCm device, MTA now converts that same checkpoint with audio-separator's existing onnx2torch dependency and runs its forward pass on PyTorch's cuda device API for ROCm. The original segment dimensions, model selection and output labeling are retained. This is shared by native/local and queued server adapters. CPU, NVIDIA and checkpoint-based RoFormer routes retain their existing behavior. Conversion failures stop explicitly instead of silently continuing on CPU.

The forward pass runs in the existing job subprocess and profiler scope. No changes weaken cgroup isolation, artifact checks, accounting attribution or GPU billing validation; device configuration is not proof of verified GPU consumption. Failed/invalid measurements remain non-billable.

## Evidence and limits

The retained ROCm regression tests exercise the same selected ONNX checkpoint through model doubles, expected output shape, device dispatch and explicit conversion failure. They do not establish audio quality, GPU consumption or deployment compatibility for an installed model. Historical validation archives remain historical evidence; they do not reactivate removed workflows.
