# ROCm / CUDA MR-MT3 device synchronization — r210

The offline runner now sets `MRMT3Adapter.device_str` to the resolved
PyTorch device after moving the model to that device. The upstream adapter
uses this field to move input features during `forward()`. Without this
assignment, the adapter defaults to CPU and ROCm raises a tensor device
mismatch when its weights reside on `cuda:0`.

La correzione sincronizza `device_str` dell'adapter con il dispositivo
selezionato, senza modificare modelli, licenze o checkpoint.

Validation: source checks and tests, plus an actual server rerun required.
Do not mark full 10–16 instrument accuracy validated until the completed
benchmark is evaluated against the original MIDI.
