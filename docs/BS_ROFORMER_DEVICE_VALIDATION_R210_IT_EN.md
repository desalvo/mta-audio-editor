# BS RoFormer r210 — verifica del dispositivo / Device validation

11 novembre / November 2026. Versione / Version: 0.3.0-r210.

## IT

L'installazione gestita risolve `Auto` una sola volta. La stessa scelta CPU,
CUDA o ROCm viene usata per installare PyTorch, verificare il dispositivo e
registrare il runtime attivo. Non viene sostituita silenziosamente con CPU se
il dispositivo selezionato non funziona.

Prima dell'attivazione, il processo isolato della fase `strict-model-load`:

1. Verifica che il backend PyTorch corrisponda alla scelta.
2. Per CUDA/ROCm verifica la disponibilità della GPU nel processo del worker.
3. Esegue una moltiplicazione di matrici sul dispositivo e ne controlla il
   risultato finito e numericamente corretto; sincronizza la GPU.
4. Carica il checkpoint in CPU con `weights_only=True` e `strict=True`,
   controlla i quattro strumenti e trasferisce il modello sul dispositivo
   richiesto, sincronizzando nuovamente.

Un errore di backend, permessi/disponibilità GPU, kernel, memoria o trasferimento
fa fallire l'installazione prima di pubblicare la nuova ricevuta. Il runtime e
il checkpoint precedenti sono conservati; il candidato fallito viene rimosso.
L'annullamento prima dell'attivazione conserva il comportamento esistente.

Il risultato e la nuova ricevuta registrano `device_validated=true`; le
ricevute preesistenti senza questo campo restano utilizzabili e riportano
`device_validated=false`. Reinstallare per eseguire la nuova verifica.
Questo dato riguarda il momento dell'installazione, non controlla continuamente
lo stato dei driver e non certifica l'inferenza neurale: `inference_tested`
rimane `false`. Sono ancora necessari inferenza sul nodo reale, confronto A/B
e ascolto. Il calcolo usa `cuda:0` anche con ROCm, secondo l'API PyTorch HIP.

Le prove locali usano backend sintetici e calcolo NumPy per esercitare il
programma di verifica, oltre ai test di installer, rollback, API e separazione.
Non costituiscono una prova hardware CUDA/ROCm o un caricamento dei pesi reali.

## EN

Managed installation resolves `Auto` once and uses that same CPU, CUDA or ROCm
choice for package installation, validation and the activation receipt.
Before activation, the isolated `strict-model-load` phase checks the PyTorch
backend, GPU availability when requested, finite and correct matrix computation,
GPU synchronization, strict weights-only checkpoint loading and model transfer
to the selected device. ROCm uses PyTorch's `cuda:0` interface.

Backend, device access, kernel, memory and transfer failures abort activation,
preserving the previous runtime and checkpoint and removing the failed
candidate. Cancellation before activation retains the existing rollback.
New receipts and results report `device_validated=true`. Older receipts remain
usable and report false until reinstalled. Validation describes installation
time; it does not continuously monitor the device or certify neural inference.
`inference_tested` remains false. Real-node inference and A/B listening remain
required. Local tests use synthetic backends and NumPy arithmetic, not real GPU
execution or real checkpoint loading.

## Fonti tecniche / Technical sources

- [PyTorch HIP semantics](https://docs.pytorch.org/docs/stable/notes/hip.html)
- [PyTorch CUDA semantics](https://docs.pytorch.org/docs/stable/notes/cuda.html)
