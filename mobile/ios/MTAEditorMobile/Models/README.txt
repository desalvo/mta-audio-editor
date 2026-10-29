MTA iOS/iPadOS model resources — current r210 admission contract

The signed app bundle owns model-rights.json and the exact license/notice
evidence referenced there. The shipped registry is EMPTY and authorizes no real
checkpoint. No model is downloaded,bundled,compiled or executed merely because
its filename or a server fingerprint names Demucs.

After genuine independent rights review,release maintainers may include the
exact reviewed .mlmodel source or .mlmodelc inventory and matching evidence.
Run python scripts/check_ios_model_rights.py --check-bundled before building.
The iOS build downloads a baseline only when the bundled review selects that
exact source/format,and then validates the actual bytes.

Existing local files without a protected installation receipt are preserved
but cannot execute. They may be removed in the local model manager. No synthetic
test permission or automatic legacy receipt migration is supplied.

Full IT/EN implementation,migration,limits and pending Apple SDK acceptance:
docs/IOS_LOCAL_MODEL_RIGHTS_R210.md. Version0.3.0-r210 PRE-RC;RC false.
