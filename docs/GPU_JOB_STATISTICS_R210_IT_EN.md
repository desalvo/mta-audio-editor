# Tempo GPU per job / Per-job GPU time

Versione 0.3.0-r210, 12 novembre 2026. Base a77f98b, full CI 43300697757 verde.

## Italiano

Corretti due difetti riprodotti prima della modifica: un campione con soli
secondi CPU sostituiva il record diagnostico e perdeva i secondi GPU; nei job
con più fasi il totale precedente impediva di mostrare il nuovo campione
della fase attiva. Ora gli aggiornamenti parziali conservano l'altra risorsa
in una transazione e i nuovi valori sostituiscono soltanto il contributo
della fase originale, mantenendo gli altri. Non si somma due volte lo stesso
campione. Il worker pubblica un identificatore interno della fase; identità
estranee o fasi parallele ambigue non vengono usate per sostituire il totale.
L'identificatore e il contesto interno non sono esposti ai client.

Job AI usa la stessa proiezione delle risorse della coda/amministrazione.
Corretta anche l'associazione nei report di job collegati al ledger con un
identificatore diverso dal vecchio UUID deterministico, senza duplicarli.

Ogni job espone ora `gpu_statistics`, separato dai consumi:

```json
{"seconds":12.5,"estimated":true,"source":"job-duration","billable":false}
```

Si preferiscono i secondi misurati/accettati o i campioni GPU disponibili.
Quando manca la telemetria, la statistica usa la durata di esecuzione del job
e mostra **~** e **Stima durata job · uso GPU non confermato**. Il tempo in coda
non cresce come elaborazione: un job non avviato parte da 0. La stima avanza
durante l'esecuzione e si ferma alla conclusione, anche per job falliti,
annullati o interrotti. Uno zero misurato rimane zero. Le durate storiche
disponibili consentono la visualizzazione senza riscrivere il database o
rieseguire il job; una cronologia priva anche dei tempi non può ricostruire
il reale consumo e conserva una fonte esplicita di durata non disponibile.

La durata del job comprende anche CPU, caricamento, trasferimenti e
pubblicazione: **non è una misura dell'occupazione o energia GPU**. Le somme
statistiche sono somme per job/worker, non capacità esclusiva del dispositivo.
Una misura successiva più precisa può correggere una precedente stima.

Il valore è visibile nella finestra di elaborazione, nel centro Job AI,
nei report per account/token e nelle email di job/riepilogo. Le email restano
vincolate alla configurazione SMTP esistente. Aggiornate le chiavi cache degli
script nelle pagine che li usano.

**Quote e addebiti continuano a usare i contatori e le evidenze originali.**
Il fallback esiste solo nella vista `gpu_statistics`, non viene scritto in
`gpu_seconds`, `gpu_seconds_estimated`, `usage_json`, prenotazioni, consumi di
quota o outbox finanziari. Non attiva il tracking a slot o nuove tariffe.
Le stime diagnostiche reali conservano la possibilità di essere aggiornate
da campioni più precisi: non si forza un massimo tra metodi diversi.

## Verifica e limiti

- Due regressioni rosse prima del fix, conservate nel cumulativo.
- 89 casi mirati passati: campioni parziali, fasi sequenziali/parallele,
  aggiornamenti live, storico terminale, zero misurato, isolamento proprietario,
  assenza di scritture economiche, report senza duplicati e renderer Node
  originali, inclusa l'avanzata del timer senza un nuovo snapshot.
- 97 regressioni di contabilità/metering disponibili passate. Quattro prove
  aggiuntive del guardian/albero processi falliscono nello stesso modo anche
  sul checkpoint a77f98b non modificato, per assenza di prova completa
  dell'albero in questo runner. Conservati entrambi gli XML; non modificati
  test, opt-in o controlli per trasformarli in successi. La full CI esegue
  queste prove normalmente, senza le esclusioni della selezione locale.
- 58 controlli di avvio, sicurezza, inventari e gate RC passati. In totale
  244 test locali distinti passati; le ripetizioni non aumentano il conteggio.
- Ruff, compilazione e sintassi dei tre script JavaScript passano.
- Bandit 1.9.4: 191 finding, 0 HIGH / 21 MEDIUM / 170 LOW, nessuna nuova segnalazione o
  soppressione. Due B105 già presenti riguardano `token_id=None`, non segreti;
  riesaminato il contesto dei nuovi metadati. Inventari source-bound aggiornati
  dopo revisione:330 app / 584 runtime, 848 confini di esecuzione, 186 di ammissione,
  34 siti trasporto. Checker e soglie invariati.

La prova non certifica il sensore del nodo GPU dell'utente. Il dato raccolto
dipende ancora dal supporto di agent/profiler/driver; il nuovo fallback
garantisce una statistica riconoscibile quando quel dato manca. Nuova full CI
da verificare sul commit finale; nessuna promozione RC o cambio versione.

## English

Fixed two reproduced defects: CPU-only updates erased the previous GPU
diagnostic, and multistage aggregation suppressed newer active-worker samples.
Partial writes now preserve the other resource transactionally. Live updates
replace only the original stage contribution; other stages remain included.
Private stage bindings are not returned in API responses.

Every job now has a separate `gpu_statistics` view. Available measurements or
GPU observations take priority. Missing telemetry falls back to execution
duration, explicitly labeled **Job duration estimate · GPU use unconfirmed**.
Queued jobs start at 0; running estimates advance and terminal estimates stop.
Measured zero is preserved. Later observations may refine an earlier estimate.
Execution duration includes CPU/loading/transfers and is not GPU occupancy,
energy or exclusive device capacity. Historical durations are projected
without rewriting accounting data or rerunning jobs.

The view appears in the processing modal, Job AI, account/token summaries and
lifecycle/digest emails. Quotas, prices and settlement retain their original
evidence and inputs. No duration fallback enters metered usage or diagnostic
quota counters. There is no new slot-accounting or billing activation.

89 targeted and 97 available accounting regressions passed; the 4 unavailable
process-tree cases fail identically on the untouched parent checkpoint and
remain enabled in normal CI. Another 58 startup/security/inventory/RC checks
passed: 244 distinct local passes in total. Source security findings/checkers
are preserved.
No physical GPU telemetry or release-candidate acceptance is claimed.
