# Drums vs percussion — MTA 0.3.0-r210

## Italiano
Priorità: separare **batteria (drum kit)** da **percussioni diverse dal kit** (ad esempio congas, shaker, tamburelli). Selezionare `MVSep Mega 53`, spuntare separazione drums/percussioni e scegliere `Tutti` oppure un singolo gruppo. Vengono richieste le classi native `drums` e `percussion` sul mix originale; i file di uscita sono `drums_without_percussions.wav` e `percussions.wav`. Le etichette sono categorie stimate dalla rete: overlap e classificazioni imperfette sono possibili; non si promette somma perfetta né isolamento verificato. La separazione kick/snare/toms rimane distinta.

`DSP` rimane fallback locale senza checkpoint, ma separa prevalentemente transienti/corpo e non riconosce semanticamente batteria e percussioni. Intel DrumSep OpenVINO (https://huggingface.co/Intel/drumsep_mdx23c_jarredou_openvino) è pubblicato con indicazione CC BY-NC-SA 4.0, tuttavia la licenza dei pesi originari MDX23C non è verificata: NON è stato abilitato. Gli originali DrumSep restano legacy bloccati; un uso gratuito/local-only non risolve la mancanza di diritti.

Prerequisiti Mega 53: runtime e checkpoint ufficiale installati dal gestore, checksum verificato, policy MIT del checkpoint, risorse CPU/GPU sufficienti. Non verificati in questo ambiente l'inferenza reale o un confronto con stem annotati.

## English
Priority: distinguish **drum kit** from **non-kit percussion** (congas, shakers, tambourines). Choose `MVSep Mega 53`, enable the drums/percussion split, then select `All` or an individual group. MTA requests the native `drums` and `percussion` classes on the original mix and writes `drums_without_percussions.wav` and `percussions.wav`. Outputs are model estimates, potentially overlapping, and are not guaranteed to reconstruct the input. Individual kick/snare/toms extraction is separate.

`DSP` remains a no-checkpoint fallback, but its transient-based division is not a semantic drum/percussion separator. The Intel OpenVINO DrumSep derivative is tagged CC BY-NC-SA 4.0 but the upstream MDX23C weight grant is unverified, so it remains disabled. Original DrumSep checkpoints remain blocked pending adequate rights. A free/local-only setting does not itself grant missing rights.

Mega 53 requires operator-installed runtime/checkpoint, SHA-256 verification and sufficient compute. No real-checkpoint inference or music-quality benchmark was conducted in this environment.
