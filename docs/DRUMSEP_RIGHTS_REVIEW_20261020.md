# Drum separation checkpoint rights / Diritti dei checkpoint di separazione batteria

## English
- **inagoy/drumsep**: MIT repository code; do **not** infer that the original pretrained drum separation weights are explicitly licensed MIT. A third-party conversion (`splitzo/drumsep`) labels the ONNX MIT, but this cannot grant rights the converter did not hold. Consult https://github.com/inagoy/drumsep and https://huggingface.co/splitzo/drumsep.
- **MDX23C DrumSep (aufr33/jarredou)**: a separate checkpoint family; openmirlab reports no author-issued terms for weights, even though framework code is MIT. Mirror labels disagree. See https://github.com/openmirlab/mdxnet-infer and https://github.com/inagoy/drumsep/issues/8.
- **Allowed path**: Mega 53 (author-declared MIT rights on exact v1.0.21 weights), SAM Audio subject to its own license, and MTA DSP. Mega 53 can return kick/snare/toms/hi-hat/percussion, but not a guaranteed separate cymbals stem. Keep original DrumSep models disabled pending proof of rights, and never treat fee waiver or administrator consent as license.
- Server: remote `drumsep` jobs choosing `mvsep-mega53` are now admitted against the Mega 53 policy, *not* the default blocked DrumSep weights policy. Exact original ONNX continues using `drumsep-weights`.

## Italiano
- **inagoy/drumsep**: la MIT del repository copre il codice; non dimostra da sola la licenza degli specifici pesi. La conversione ONNX di Splitzo dichiara MIT, ma non può concedere diritti non detenuti.
- **MDX23C aufr33/jarredou**: famiglia separata di checkpoint; la licenza commerciale dei pesi non è documentata dagli autori. Le indicazioni dei mirror sono discordanti.
- **Alternative utilizzabili secondo policy**: Mega 53 (diritti MIT dichiarati dall'autore per i pesi v1.0.21), SAM Audio con licenza specifica, DSP MTA. Mega 53 offre kick/snare/toms/hi-hat/percussioni, senza garantire cymbals separati.
- L'opzione Mega 53 nei job remoti utilizza ora la policy di Mega 53; i checkpoint DrumSep originali restano bloccati finché non emerge una concessione valida. La rinuncia al billing non sostituisce una licenza.


## Additional original-source verification (2026-10-20)

- inagoy repository MIT: https://github.com/inagoy/drumsep/blob/main/LICENSE — applies to the repository software; the upstream README links externally hosted weights without an explicit weight grant.
- Weight licensing question to inagoy: https://github.com/inagoy/drumsep/issues/9 — no unambiguous public authorization for commercial weight use established by this review.
- Separate MDX23C licensing question: https://github.com/inagoy/drumsep/issues/8 — refers to aufr33/jarredou, NOT inagoy's Hybrid Demucs checkpoint.
- Splitzo ONNX: https://huggingface.co/splitzo/drumsep — third-party MIT tag and attribution document conversion but do not independently confer upstream checkpoint rights.
- OpenMIRLab source and mirrored checkpoint integrity: https://github.com/openmirlab/mdxnet-infer/releases/tag/weights-drumsep-v1 — MDX23C 6-stem SHA-256 d2a4aa53eb584d21eead358a4e66d1882ad182911be018f052b5da73be9096d0. This is an **identity** digest, not proof of permission.
- OpenMIRLab weighs commercial rights as unresolved: https://github.com/openmirlab/mdxnet-infer/blob/master/README.md . Third-party mirrors disagree and the original grant is missing. Their phrase “non-commercial-safe” describes risk posture, not a verified NC license grant.

**Release gate:** do not enable these original checkpoints merely via free-only billing, noncommercial server mode or double administrator consent. A valid grant, or a genuinely different checkpoint with verified rights, is required. MTA's Mega 53, SAM Audio and DSP implementations remain functional alternatives subject to their own licensing/deployment checks.
