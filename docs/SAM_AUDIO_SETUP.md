# Optional SAM Audio integration / Integrazione SAM Audio opzionale

SAM Audio is **not** bundled. Its model weights require explicit gated access and are subject to the [SAM License](https://github.com/facebookresearch/sam-audio/blob/main/LICENSE). The official repository recommends a CUDA GPU. Inference without CUDA may be slow or unsupported in particular configurations. Do not distribute model weights in MTA packages.

## Installation (English)

1. Request access to your selected checkpoint (`facebook/sam-audio-small`, `-base`, or `-large`) from Meta on Hugging Face, then authenticate using `hf auth login` in the same environment where the worker will run.
2. Create a dedicated Python >= 3.11 environment and install the [official SAM Audio repository](https://github.com/facebookresearch/sam-audio) using its documented installation instructions.
3. Set the `MTA_SAM_AUDIO_PYTHON` environment variable to that environment's absolute `python` executable path before starting MTA Audio Editor.
4. From Stem Separation select **SAM Audio Small/Base/Large** under percussion method and select **Percussions**, **Kick**, **Snare**, **Toms** or **Cymbals**. The selected method is remembered across projects. If SAM is missing, the operation fails with a clear error; it does not silently fall back to DSP.
5. Checkpoints are cached by Hugging Face in `HF_HOME` if set, otherwise usually `~/.cache/huggingface`. Use `HF_HOME` to control location. The original project audio files remain in the MTA project folder.

Demucs first isolates the drum stem. Kick/Snare/Toms/Cymbals are extracted from this stem using separate SAM prompts. Non-kit percussion is extracted from the original mix because it may not be in Demucs' drums stem. **Drums without percussions** uses Demucs' drums estimate, not guaranteed to exclude every hand percussion. Results are estimates and may contain bleed. Selecting one output still permits the upstream Demucs step but imports only the requested result.

## Installazione (Italiano)

1. Richiedere e ottenere l'accesso al checkpoint SAM Audio su Hugging Face e autenticarsi con `hf auth login` nell'ambiente del worker.
2. Creare un ambiente Python >= 3.11 separato e installare SAM Audio dal repository ufficiale. È raccomandata una GPU CUDA.
3. Impostare `MTA_SAM_AUDIO_PYTHON` con il percorso assoluto dell'interprete Python di tale ambiente prima di avviare MTA Audio Editor.
4. Nelle opzioni di separazione scegliere SAM Audio Small/Base/Large e il solo strumento desiderato. La preferenza è globale e persistente.
5. I checkpoint sono conservati nella cache Hugging Face (`HF_HOME`, oppure normalmente `~/.cache/huggingface`). Non sono inclusi negli installer MTA.

Il primo passaggio Demucs resta necessario; il risultato SAM Audio usa un prompt dedicato. Non tutte le percussioni vengono isolate perfettamente. Il DSP rimane disponibile come metodo alternativo selezionabile, senza spacciarlo per AI.

## Autenticazione del servizio server / Server service authentication

Il server verificato usa `root` e `HF_HOME=/var/lib/mta/models/huggingface`, senza `HF_TOKEN` o `HF_TOKEN_PATH` nell’ambiente. Il runtime SAM era `/opt/mta/ai-7f176167db5671ae/sam/bin/python`; il percorso è specifico dell’installazione e può cambiare. Le istruzioni complete per verificare l’utente e le variabili effettive senza esporre token, autenticare il runtime, controllare l’accesso ai repository gated Base/Large e diagnosticare 401/403 sono nel manuale amministratore IT/EN, online e PDF, sezione “SAM Audio: accesso e diagnosi del servizio”. Verificare approvazione e condizioni del modello con l’account usato dal servizio.

The inspected server uses `root`, `HF_HOME=/var/lib/mta/models/huggingface` and no `HF_TOKEN` or `HF_TOKEN_PATH` in its environment. Its SAM runtime was `/opt/mta/ai-7f176167db5671ae/sam/bin/python`; this path is installation-specific and can change. The IT/EN online and PDF administrator manuals contain the complete procedure to inspect the effective service user and environment without exposing tokens, authenticate the runtime, check gated Base/Large access and diagnose 401/403. Check model approval and terms using the service account.
