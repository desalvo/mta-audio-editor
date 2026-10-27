# Singing configuration byte binding — 2026-10-26 — PRE-RC

Restored the last complete cumulative SHA256 f68cc31f69de2ebee6d2f52d141d3ab84309254aa27948b534ffb4998319386f into a clean workspace and verified every manifest byte/hash/mode before editing. No Git commit was made; cumulative changes still start after9fc85ce79bee9871696dea9396565395a415aa72. No previous validated product test was rerun merely because scratch storage expired.

## Implemented path

DiffSinger ONNX now parses the exact verified bytes of its inventory, acoustic/vocoder YAML configurations, phone map and language map. Previously the file was verified and subsequently reopened for parsing. The existing shared bounded descriptor/hash reader now supplies the parser input, keeping path confinement/component policy checks intact. The ONNX inventory limit remains4MiB; YAML/maps are bounded to1MiB. ONNX acoustic/vocoder sessions retain the previous exact-byte loading fix.

The shared DiffSinger bridge likewise parses exact verified lexicon bytes and uses exact verified flattened native configuration bytes for its own vocoder-selection check. Original bank-specific lexicon/language checks and permissions remain. This **does not** make native OpenVPI's subsequent opaque runtime loads verified: external runtimes still need their own supported load binding. No commercial remote execution or regime-switching permission is added.

## Verification

40 distinct affected cases pass,8 new,zero unresolved failures/errors/skips. Exact reports and source hashes:validation/r210/singing-loaded-result.json. Tests exercise the actual singing run entry, YAML/JSON parsing, binding checks, both synthetic sessions and real resampling/WAV writing. Four post-inventory substitutions (acoustic config,vocoder config,phones,languages) fail before any model session/output; mismatched manifest bytes and a lexicon swap after path verification are refused. The positive case passes the original acoustic/vocoder hashes to both sessions and emits a real48000Hz WAV. Sessions are explicit doubles, not neural synthesis or voicebank certification. Prior actual ONNX Runtime/synthetic graph proof remains valid for the unchanged model-byte reader; no ONNX dependency was reinstalled for this batch.

Current unsuppressed Bandit1.9.4 covers287 app Python files and165 reviewed findings(0 high/21 medium/144 low). One unchanged fixed operator-owned subprocess warning moved from DiffSinger bridge line192 to191;its existing disposition was rebound to that exact unchanged call. Checkers/suppressions unchanged. Source-bound gate,Ruff and changed Python compilation pass. Requirements-dev was restored in an isolated environment to run these affected cases;no product dependency changed. No provider,GitHub or real server mutation,stage/commit/push/tag/release occurred.

## Open original acceptance

Original criteria remain23/42(54.8%),0/7 whole macroareas;RC false and switching disabled. F3/F4/F6 still require executing-load coverage of remaining adapters/transports, authenticated remote loaded identity protocol and independent installed-checkpoint rights. These are not all external prerequisites. Prior managed installed-inventory and Basic Pitch/DiffSinger ONNX loader fixes are complete at their documented boundaries and should not be repeated.

Next code work: remaining checkpoint loaders (including Transkun), executable configuration/runtime load boundaries and authenticated process-bound exchange; deny opaque unsupported commercial execution. Continue global finance/integrated cutover work independently of unavailable provider/hardware targets. Missing real voicebanks or native targets do not explain away unfinished protocol implementation.

IT: conservare i digest fissati dagli asset revisionati;non sostituirli con hash forniti dal client. Un rifiuto richiede la verifica del pacchetto,non l'esclusione dei controlli. EN: retain reviewed pinned digests;investigate rejected bundles without bypassing validation.
