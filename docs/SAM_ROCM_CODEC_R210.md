# SAM Audio: TorchCodec su ROCm — 0.3.0-r210

Il log EL10 del 17 ottobre 2026 mostra Torch 2.11.0+rocm7.2 e una wheel TorchCodec che cerca libnvrtc.so.13. La selezione predefinita Linux di TorchCodec può introdurre binari CUDA anche se Torch è ROCm.

L'installer seleziona TorchCodec 0.11.1+cpu dall'indice ufficiale CPU per il runtime SAM ROCm; per il runtime Torch CPU 2.14 seleziona 0.17.0+cpu. Il vincolo esatto della variante viene mantenuto durante la risoluzione delle dipendenze SAM. La decodifica CPU non cambia il dispositivo di inferenza. L'ambiente CUDA mantiene il percorso precedente.

La verifica SAM include una decodifica WAV PCM di 100 ms con AudioDecoder: errori delle librerie condivise bloccano il marker ready e la pubblicazione della configurazione. Restano i controlli di import, operatore torchvision e tensore GPU. Il fingerprint include il codice installer: questa modifica crea nuovi runtime senza sostituire quelli attivi.

Il warning xFormers nel log è distinto dall'eccezione TorchCodec: non viene nascosto e non si installano librerie NVIDIA per mascherarlo. La disponibilità dei kernel xFormers e l'inferenza reale SAM su gfx1151 richiedono ancora una prova sul server; non sono certificate dalla regressione locale.

## Applicazione

Dopo aver compilato e installato il nuovo RPM, eseguire dalla root del progetto:

```bash
sudo bash scripts/install_mta.sh --configure-only --unattended
```

Se l'RPM non è stato ricompilato, il wizard usa ancora la copia sotto `/usr/lib/mta-audio-editor-server/native-installers/`. Per una correzione temporanea, dalla root del progetto aggiornato:

```bash
sudo cp -a /usr/lib/mta-audio-editor-server/native-installers/install_ai_engines.py /usr/lib/mta-audio-editor-server/native-installers/install_ai_engines.py.bak
sudo install -m 0644 scripts/install_ai_engines.py /usr/lib/mta-audio-editor-server/native-installers/install_ai_engines.py
sudo bash scripts/install_mta.sh --configure-only --unattended
```

Non cancellare gli ambienti attivi; il wizard conserva il checkpoint se una fase fallisce. Nessuna modifica al billing.

Fonti ufficiali: https://github.com/meta-pytorch/torchcodec (installazione CPU e matrice Torch/TorchCodec), https://download.pytorch.org/whl/cpu/torchcodec/ (wheel CPython 3.12 x86_64 delle due versioni verificate disponibili).

## Documentazione

Spostati in docs i 21 Markdown non README che si trovavano nella root. Aggiornato l'indice README e i riferimenti; test di regressione impedisce nuovi Markdown non README nella root.
