# ChordFormer, UVR and DrumSep — checkpoint review (2026-10-20)

MTA version **0.3.0-r210**. The Studio `commercial-service` switch guards **cost-recovery model admission**, but does **not** globally disable unrelated paid subscriptions, invoicing, or paid API offerings. Those require separate shutdown and acceptance testing to establish a genuinely noncommercial environment. Double confirmation is mandatory. Unverified checkpoints remain disabled by default.

* **ChordFormer:** the five checkpoints and the precise MTA fork lack verified rights for the actual weight files. Keep disabled until per-file license, hash and deployment authorization are documented; noncommercial mode is not a replacement for absent rights.
* **UVR `UVR_MDXNET_KARA_2.onnx`:** upstream asks third-party developers to provide MIT attribution, but open upstream issue #2185 specifically requests clarification for this exact ONNX. Keep disabled pending authoritative per-checkpoint clarification/permission.
* **DrumSep:** original `inagoy/drumsep` repository and `splitzo/drumsep` ONNX conversion declare MIT, but the precise MTA mirror `gridshiftstudio/drumsep-onnx` still requires identity, SHA-256 and chain-of-title confirmation. Prefer verified original weights or documented conversion once established.

Viable workarounds: select a verified-licensed replacement checkpoint; seek written permission from the rights holder; or deploy in a genuinely noncommercial environment **only if the weights' actual terms permit it**. No charge and two operator confirmations cannot invent a missing license. Subscriptions, paid APIs and invoicing must be isolated separately.

Tests cover local admission and switch behavior only; live financial flows, native/browser production environments, ROCm and legal resolution of checkpoints remain pending.

Sources: https://github.com/mwaseemrandhawa/ChordFormer ; https://github.com/Anjok07/ultimatevocalremovergui/blob/master/README.md ; https://github.com/Anjok07/ultimatevocalremovergui/issues/2185 ; https://github.com/inagoy/drumsep ; https://huggingface.co/splitzo/drumsep
