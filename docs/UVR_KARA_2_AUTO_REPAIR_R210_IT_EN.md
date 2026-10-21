# UVR KARA 2 — repair all'avvio / startup repair (0.3.0-r210)

## Italiano
La riparazione automatica all'avvio è abilitata per impostazione predefinita (`MTA_UVR_KARA2_AUTO_REPAIR=1`) **solo per un modello già ammesso dalla policy licenze**. Un checkpoint mancante o con SHA-256 diverso da `bf32e15105a09c0f7dddd2b67346146334d6f3ecb399ed7638eba2ab07cbf5f4` viene riscaricato tramite il gestore `audio-separator` preesistente nel runtime AI. Il file viene prima scaricato in una directory temporanea, verificato e spostato atomicamente. Symlink rifiutati. Nessun download o activation automatica se manca l'autorizzazione applicabile. Per disabilitare: `MTA_UVR_KARA2_AUTO_REPAIR=0`.

**Licenza:** il README upstream UVR invita a rispettare MIT e attribuire gli autori quando si usano i modelli in app terze; la concessione specifica sui pesi KARA 2 non è confermata. Assenza di divieto e uso gratuito non sono una licenza. https://github.com/Anjok07/ultimatevocalremovergui/issues/2185

## English
Startup self-repair is enabled by default (`MTA_UVR_KARA2_AUTO_REPAIR=1`) **only for checkpoints already admitted by the license policy**. A missing or SHA-256-mismatched checkpoint is downloaded via the existing `audio-separator` manager in the AI runtime, into a temporary directory; the pinned fingerprint is verified before an atomic replacement. Symlinks are rejected. No download or automatic activation occurs without an applicable authorization. Disable with `MTA_UVR_KARA2_AUTO_REPAIR=0`.

**License:** the UVR upstream README requests MIT notice and credits for models in third-party apps, but exact KARA 2 weights licensing is not conclusively established. Free operation or lack of a prohibition alone does not grant permission. https://github.com/Anjok07/ultimatevocalremovergui/issues/2185
