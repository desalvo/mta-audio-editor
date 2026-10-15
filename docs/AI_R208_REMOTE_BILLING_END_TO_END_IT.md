# Billing remoto Arranger/Remix: chiusura end-to-end (r208)

## Problema individuato

Il bridge di metering persisteva evidenze CPU di origine `remote-worker`, ma
l'Outbox contabile e le due API di finalizzazione del ledger accettavano solo
`worker`, `cgroup` o `gpu-agent`. L'errore impediva di consegnare un settlement
remoto autenticato al ledger.

## Correzione

La sorgente `remote-worker` è ora esplicitamente consentita nei tre confini
contabili: validazione dell'Outbox, finalizzazione normale del ledger e
finalizzazione idempotente. La validazione dei periodi contabili accetta
`remote-worker` come misura CPU. Non sono consentiti `gpu_seconds` o
`gpu_energy_joules` con questa sorgente: i dati GPU richiedono ancora una
misurazione separata e attendibile di origine `gpu-agent`.

## Contratto e garanzie

* Le evidenze devono essere acquisite a monte da una attestazione remota
  verificata: accettare una etichetta `remote-worker` non autentica da sé i dati.
* Il bridge rende immutabile l'evidenza e richiede un job Arranger/Remix durevole
  con proprietario autenticato.
* Il provisioning riusa il job ledger deterministico; l'Outbox è idempotente;
  `deliver()` conferma il settlement, con replay sicuro.
* Un errore di verifica o di consegna non deve consentire il rilascio di audio
  fatturabile. Il gateway di esecuzione controlla la registrazione prima del
  ritorno dei byte; la pubblicazione resta protetta dal gate di finalizzazione.

## Test

`tests/test_r208_remote_billing_e2e.py` verifica Outbox, validazione GPU,
settlement e replay con database di autenticazione e ledger reali.

## Ambito

Questo intervento chiude il blocco di integrazione contabile nel percorso
**Arranger/Remix remoto**. Non certifica automaticamente tutti gli altri adapter,
né i benchmark hardware ROCm, né la misura GPU per singolo job.
