# Runtime AI e pubblicazione Mega53 / AI runtime and Mega53 publication

12 novembre 2026. Versione **0.3.0-r210, PRE-RC**.
Base verificata: `17e6a8cfd3b628fa38b65febe1feddc6bb9f5808`, full CI43259970098 verde.

## Italiano

Completato il blocco software di installazione AI e pubblicazione Mega53.
La verifica reale dell'installer ha rilevato due errori che la precedente CI
generale non esercitava: TorchAudio2.14.1 non pubblicato e include relativo
requirements-vst3.txt risolto nella cartella del virtualenv anziché nei sorgenti.
L'installer conserva ora gli include annidati e i percorsi con spazi.

Il runtime server CPU usa Torch2.14.1+cpu, TorchAudio2.11.1+cpu,
TorchVision0.29.1+cpu e TorchCodec0.17.0+cpu. TorchAudio ha un ciclo di
versione/ABI indipendente. CUDA server e Mega53 usano il gruppo pubblicato
Torch/TorchAudio2.11.0+cu128, TorchVision0.26.0+cu128; il codec server CUDA
è0.11.1+cpu. L'inferenza conserva la GPU selezionata, la decodifica è CPU.
ROCm conserva2.11.0+rocm7.2 e codecCPU0.11.1. I runtime esistenti non sono
sostituiti automaticamente; l'attivazione resta successiva alla verifica.

Mega53 seleziona l'acceleratore una sola volta e lo vincola a pacchetti,
probe e ricevuta. Prima dell'attivazione verifica backend, disponibilità,
calcolo, sincronizzazione, caricamento rigoroso e trasferimento del modello.
Una ricevuta vecchia non viene dichiarata retroattivamente device_validated.
Il processo di inferenza usa -I, ambiente filtrato e root upstream esplicito;
il test con processo reale impedisce l'esecuzione di sitecustomize viaPYTHONPATH.
Questo isolamento non autentica interprete, dipendenze, .pth o checkout.

Le uscite Mega53 locali (voci e batteria) e gli stem remoti sono preparati
prima della pubblicazione. Collegamenti esclusivi impediscono sovrascritture.
Errore, collisione, annullamento o revoca locale dei diritti rimuovono soltanto
i file ancora appartenenti all'operazione, confrontando device/inode.
Le sostituzioni concorrenti sono conservate. La policy remota resta sul worker
originale; non è sostituita da quella del client. Servono hard link sul
filesystem di destinazione. Il gruppo non è atomico in caso di crash o
perdita di alimentazione; rimane la transazione di registrazione progetto.

## Verifiche effettuate

- **127 regressioni funzionali passate**, nessun fallimento o skip: include
  processo Mega53 sintetico reale, PCM/filesystem reali, concorrenza,
  annullamento, revoca e fixture esplicite per backend/modello.
- **Installazione completa CPU reale**, senza scaricare checkpoint: import
  di tutti i motori del catalogo, TorchCodec/FFmpeg, salvataggio/lettura stereo
  non silenziosa con confronto campioni, backendCPU e NMS compilato su box
  effettivi. Freeze e log sono nel cumulativo. Il compilatore di questo
  ambiente richiedeva CC=gcc/CXX=g++; il tentativo precedente con clang
  assente è conservato come limite ambientale risolto, non come prova positiva.
- Nuovo job CI installa il runtime CPU completo attraverso il CLI reale,
  verifica il marker finale e conserva log/freeze. Non equivale a inferenza
  neurale, GPU o accettazione della distribuzione su tutti i target.
- Ruff, compilazione, whitespace e inventari riesaminati. Bandit1.9.4:
  **191finding,0HIGH/21MEDIUM/170LOW**, nessun nuovo finding o soppressione.
  Tre identità B603 cambiano soltanto per gli offset dopo il nuovo probe.
  Nessun checker, soglia, criterio RC, peso o denominatore è indebolito.
- Le prove esterne eseguite qui registrano **3skip espliciti**: due provider
  senza opt-in/database sandbox e un test senza cgroup delegato. Non sono pass.

## Stato RC e impedimenti reali

**34/42 = 81,0% della checklist RC**, non percentuale dell'intero prodotto.
Nessuno degli otto criteri residui è promosso con questo blocco software.
La precedente stima globale73% resta storica e non viene ricalcolata.

| Criterio | Evidenza ancora necessaria |
| --- | --- |
| A6 | Sandbox Stripe/PayPal isolate e configurate, interi cicli canonici, notifiche e readback ledger/cassa |
| B6 | Autorità e worker su host indipendenti, perdita/partizione/drain senza doppia esecuzione |
| C6 | Integrazione e crash/transizioni concorrenti fra host indipendenti; non chiusa dalle prove locali |
| F4 | Contratti indipendenti per interpreti/dipendenze e backend ACE effettivo, copertura nativa/opaca residua |
| F5 | App installate sui sistemi supportati e garanzie non commerciali verificate |
| F6 | Revisione indipendente completa dei checkpoint opzionali effettivamente installati e diritti del deployment |
| G5 | Esecuzione/restart/storage/ingress su Docker, Podman e Kubernetes; le build verdi coprono solo una parte |
| G6 | App Windows/macOS, modelli GPU, plugin VST e hardware/audio/ascolto reali |

Questo runner non dispone di Docker, Podman, kubectl, GPU, cgroup delegato,
copia sandbox o accesso configurato a host di collaudo indipendenti.
La campagna esterna va eseguita su ambienti isolati accessibili o dal loro
operatore, conservando versione, artifact hash, configurazione senza segreti,
comandi, esiti e casi non eseguiti. Non inserire credenziali nei rapporti.
Procedure esistenti: RC_EXTERNAL_ACCEPTANCE_R210.md,
A6_SANDBOX_PREREQUISITES_R210.md e scripts/verify_music_hardware.py.
F4/C6 comprendono ancora implementazione/integrazione: non sono riclassificati
come soli problemi di hardware. Non è possibile dichiarare la RC da questi
esiti. Nuova full CI e matrice server richieste sul commit finale; i risultati
della base non attestano il nuovo commit.

## English

Fixed two real full-installer failures: unpublished TorchAudio2.14.1 and a
nested requirements include resolved from the generated venv file. CPU now
uses published stable-ABI TorchAudio2.11.1 with Torch2.14.1; CUDA uses the
coherent2.11.0/cu128 family and CPU decoding. Existing installations are not
silently replaced. A real complete CPU installation passed all catalog
imports, FFmpeg/TorchCodec, nonzero stereo round-trip and compiled NMS.
CI now runs that full installation rather than relying only on generic tests.

Mega53 binds a single selected accelerator through install, computation/model
probe and receipt. Inference startup is isolated; local vocal/drum and remote
drum publication never overwrite outputs and roll back owned links after
failure/cancellation/local rights revocation. Concurrent replacements survive.
This needs hard links and is not group crash-atomic or model-quality proof.

127 distinct functional cases pass. Three unavailable external cases are
explicit skips. Security findings and all original RC criteria are preserved.
RC checklist remains34/42(81.0%); A6/B6/C6/F4/F5/F6/G5/G6 remain open, including
the independent runtime/backend contracts and cross-host integration work.
No release candidate tag/promotion is made. Final main CI must still verify
this batch; the previous green run belongs to its parent revision.

## Fonti primarie / Primary sources

- https://github.com/pytorch/audio/releases/tag/v2.11.1
- https://github.com/pytorch/pytorch/releases/tag/v2.14.1
- https://github.com/pytorch/vision/releases/tag/v0.29.1
- https://download.pytorch.org/whl/cpu/torchaudio/
- https://download.pytorch.org/whl/cu128/torch/

