# Validazione 0.3.0-r210 — GPU live e worker AI

Data: 2026-10-16. Base cumulativa: MTA-r210-profiler-startup.zip,
SHA-256 d00e4338ce8de753cb8fe9da71177cb408a7ed84b95495cc66fbe9277caa1b60.
Ultimo commit utente rilevato: d3be8838dafadfb756b2a25d4adb16a5eb27af65.
Nessun commit, push, tag, release o aggiornamento di servizi eseguito.
VERSION=0.3.0; REVISION=210.

## Modifiche

- ACE: finestre cooperative del profiler sul thread di inferenza, campioni
  parziali tramite polling HTTP e secondi GPU diagnostici nell’Arranger.
- Rimozione hook e arresto profiler anche in caso di errore; nessuna ripetizione
  della generazione; bypass durante graph capture del compilatore.
- Wrapper nel vero processo Demucs/SAM e raccolta comune dei worker PyTorch
  unificati; somma delle chiamate sequenziali e identità assegnata dal server.
- Report piccoli, atomici e limitati, separati dai consumi; consultazione admin
  e inclusione nello ZIP diagnostico. Nessuna abilitazione del billing GPU.
- Conservazione del valore ACE finale alla riapertura dell’Arranger.

## Controlli

Regressione generale: 3297 passed, 4 skipped, 10 deselected, 4 warnings;
128.61 s; coverage app 74.36% (soglia richiesta 70%). I quattro skip richiedono
SDK Steinberg/ADelay opzionali. I dieci casi esclusi riguardano integrazioni
AF_UNIX non eseguibili in questo ambiente. Comando e risultati completi nei log
r210-live-gpu-full.log e XML associati.

Dopo la regressione generale sono stati rifiniti il bypass del compilatore e
il callback finale (nessun controllo cancellazione dopo il regolamento ledger),
e aggiunti due casi CLI. I controlli mirati finali sul codice consegnato:
68 passed, 1 warning, 6.03 s. Comprendono profili parziali/finali, thread,
cleanup/errori, CLI child process, identità server, autenticazione admin,
persistenza, esclusione billing e polling/UI. Evidenza in targeted.log/XML.

Ruff su app/native/tests e scripts/k8s-wizard.py: All checks passed.
Node --check su app/static/app.js e JavaScript inline AI Billing: superato.

## Limiti e accettazione hardware

Nessuna GPU ROCm disponibile nel runner. Gli eventi dei test sono simulati;
sono stati eseguiti anche subprocess reali CPU e CLI con backend di prova.
La precedente prova reale ACE ha prodotto 66.898005 secondi kernel diagnostici
ed audio riproducibile/persistente, ma usava la raccolta finale precedente.
I nuovi campioni durante inferenza, overhead, concorrenza e singoli backend
richiedono prova sul server. La prova lunga dell’utente non è stata interrotta.
Windows e certificazione completa r210 restano da concludere.

I campioni non sono garantiti ogni cinque secondi: dipendono dai checkpoint
PyTorch; modelli compilati o runtime diversi possono aggiornarsi solo alla fine.
Runtime esterni/ONNX e percorsi legacy non sono automaticamente coperti.
GPU diagnostica non fatturabile: nessuna misura non valida diventa consumo.
Istruzioni: LIVE_GPU_AND_AI_WORKERS_R210.md.
