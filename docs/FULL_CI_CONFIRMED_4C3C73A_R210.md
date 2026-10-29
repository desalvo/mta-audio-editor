# Full CI confermata — 4c3c73a — MTA 0.3.0-r210 PRE-RC

28 ottobre 2026 · fuso Europe/Rome

## Esito e nuova baseline

L'utente ha confermato il commit e il run, verificati in sola lettura tramite GitHub:

- Commit: `4c3c73afe6d3829aad155c23f5f1bbb6d375433a`, messaggio `Fix Stripe refund test fixtures for canonical paid history [full-ci]`, creato il 27 ottobre 2026 alle 21:07:11 UTC (22:07:11 Europe/Rome).
- Full CI: https://github.com/desalvo/mta-audio-editor/actions/runs/40584085026
- **14 job riusciti, zero fallimenti, un job di pubblicazione su tag saltato**. Nessun job annullato. Non si interpreta un job saltato come prova positiva.
- Quality e unit test, job `122470833556`: **6887 passati, 114 skip, zero fallimenti/errori**, 1016 warning; durata pytest **1331,27 s (22 min 11 s)**. Copertura **76,88%**, soglia invariata **70%**.
- SAST e audit dipendenze, job `122470833363`: riuscito; riutilizzare questa evidenza sul sorgente invariato.
- SDK VST3 Linux, gate container, runtime Windows Chordino, DEB/RPM Linux x86_64 e arm64, installer macOS x64 e arm64 e Windows, Android APK/AAB e archivio iOS/iPadOS: job riusciti.
- Il workflow dell'utente ha completato anche pubblicazione Docker Hub e aggiornamento della prerelease rolling `early-main`. Questo aggiornamento documentale non ha effettuato pubblicazioni o altre mutazioni remote.

La fonte strutturata completa, con identità dei job, singoli step, artifact e digest, è `validation/r210/ci-4c3c73a-observation.json`. Nessun artifact binario CI di grandi dimensioni è stato scaricato per ripetere una verifica già riuscita.

## Regressione rimborsi chiusa anche in GitHub

Il precedente run `40550957081`, sul commit `5891082820d3d69bd8bd3ea0be06117d5639c135`, rimane storicamente fallito: 6818 passati, 60 falliti, 114 skip. Le sue 60 anomalie condividevano la fixture Stripe incompleta, corretta nel commit ora verde. Il conteggio è coerente: **6818 + 60 casi ripristinati + 9 nuovi controlli negativi = 6887 passati**, con gli stessi 114 skip.

Il blob Git del file `tests/test_r210_operator_refunds.py` nel nuovo commit è `b0858a770a9ee7ec327fc74a425888a7cca02ef0` e coincide esattamente con il file del cumulativo validato. Il commit contiene i 19 file attesi della riparazione: soltanto la fixture è codice eseguibile, il resto è documentazione e prove. I precedenti 156 pass locali distinti, compresi 14 casi Chromium reali, sono conservati e non rieseguiti. Nessun guard finanziario, sorgente di produzione, workflow, dipendenza, soglia o scanner è stato modificato per ottenere il verde.

Le indicazioni “conferma GitHub pendente” in `CI_STRIPE_REFUND_FIX_5891082.md`, nei vecchi rapporti e negli handoff storici sono **superate da questa osservazione**. Non riapplicare la patch della fixture: è già committata. Non ricostruire C2, E5, il recupero SQLite/export o le altre modifiche comprese nella baseline attuale.

## Limiti ed evidenze ancora mancanti

Il job iOS risulta riuscito perché produce l'archivio **non firmato**. Il log effettivo dice `Apple signing secrets not configured; skipping signed IPA.`: nessun IPA firmato è provato e l'upload opzionale TestFlight è saltato. La pubblicazione desktop/mobile su GitHub Release per tag è anch'essa saltata; è distinta dall'aggiornamento rolling `early-main`, riuscito.

La full CI non sostituisce sandbox Stripe/PayPal reali, Kubernetes/multihost, prove di diritti e NC su tutti i sistemi, modelli GPU, plugin VST reali o hardware. Le garanzie richieste dai criteri originali devono essere dimostrate nel loro intero perimetro. Build e smoke test riusciti restano prove riutilizzabili, senza promuovere automaticamente i criteri più ampi.

**Stato invariato: 25/42 criteri (59,5%), 0/7 macroaree, PRE-RC; RC non raggiunta e transizione finanziaria globale non autorizzata.** Restano 17 criteri originali: 12 di implementazione/validazione funzionale o revisione dei diritti e 5 legati a target/ambiente. Elenco e formulazioni originali: `validation/r210/release-decision-current.json`. Nessun peso, criterio o gate è stato modificato.

## Ripresa operativa

1. Usare `4c3c73afe6d3829aad155c23f5f1bbb6d375433a` come baseline committata. Questo checkpoint aggiunge **soltanto documentazione, osservazione CI e manifest**.
2. Riprendere il blocco funzionale C3 + C5 + D6 + E4: risoluzione completa delle obbligazioni, transizione sicura bidirezionale tramite API amministrativa effettiva, continuità di saldi/periodi e workflow operatore. Riutilizzare C2 ed E5 già accettati; mantenere i gate globali bloccati finché non sono provati tutti gli esiti originali.
3. Portare avanti le attività indipendenti di storia provider/legacy, identità e diritti degli esecutori, recupero con prova originale di quiescenza. Registrare separatamente i prerequisiti esterni mancanti.
4. Rieseguire soltanto i test interessati da nuove modifiche e i controlli imposti da quelle modifiche. Nessuna nuova full CI è necessaria per confermare ancora la stessa riparazione. Questo aggiornamento documentale non richiede un nuovo giro full CI.

Consegna completa: `MTA-0.3.0-r210-pre-RC-full-ci-confirmed-cumulative.zip`, con tutti i file, asset, licenze, manuali, 614 log originari e modi dei file del cumulativo precedente. Manifest completo: `validation/r210/work-source-manifest.json`; la sua voce è esclusa dal proprio hash per evitare autoriferimenti.

L'agente non ha eseguito test, commit, staging, push, tag, release, dispatch CI, richieste a provider o modifiche a server reali in questo aggiornamento. Un eventuale commit dei soli documenti può usare:

```text
Record successful full CI for commit 4c3c73a
```

## English handoff

User-confirmed full run `40584085026` is verified against commit `4c3c73afe6d3829aad155c23f5f1bbb6d375433a`: 14 successful jobs, zero failures, one tag-only publication job skipped. Quality reports 6887 passed, 114 skipped, 76.88% coverage against the unchanged 70% threshold, in 1331.27 seconds. SAST, VST3 SDK, container gate and all native/mobile build jobs succeeded. Docker Hub publication and rolling early-main update succeeded in the user's workflow. iOS produced an unsigned archive; missing Apple secrets prevented signed IPA creation and TestFlight was skipped.

The shared Stripe refund fixture regression is now confirmed resolved by GitHub. Exact committed fixture bytes match the previously validated cumulative; all production code remains unchanged by that repair. Do not reapply the historical patch or rerun unchanged local/full suites. This new checkpoint changes documentation/evidence only. Reuse accepted C2/E5 and proceed with the original C3/C5/D6/E4 functional work and other independent gaps. Acceptance remains 25/42, 59.5%, zero of seven complete macroareas, PRE-RC; no original criterion or gate was relaxed. No Git, remote, provider or production-server mutation was performed by the agent.
