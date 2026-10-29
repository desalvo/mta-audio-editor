> Aggiornamento 28 ottobre 2026: riparazione committata in `4c3c73a` e full CI40584085026 confermata verde (6887passati,114skip,76,88%). Leggere FULL_CI_CONFIRMED_4C3C73A_R210.md. Le istruzioni di applicazione/commit e la conferma pendente qui sotto sono storiche; non riapplicare la patch.

# CI40550957081: correzione delle fixture Stripe per i rimborsi

27 ottobre 2026 · MTA0.3.0-r210 PRE-RC

## Baseline e diagnosi

L'utente ha confermato il commit **5891082820d3d69bd8bd3ea0be06117d5639c135**,messaggio “Complete service admission draining and harden Stripe, transition recovery, legacy execution and export polling[full-ci]”. È la nuova baseline;il prossimo commit descrive soltanto la correzione successiva.

Run: https://github.com/desalvo/mta-audio-editor/actions/runs/40550957081

Il job Quality122354241894 termina con **60 fallimenti,6818 passati,114 skip**,in1000,85s. La coverage76,78% supera la soglia invariata70%. SAST/dipendenze e compilazione SDK VST3 sono verdi. I job successivi dipendenti da Quality sono saltati;non sono fallimenti indipendenti. La classificazione e i60 identificativi sono in `validation/r210/ci-5891082-observation.json`.

Tutti i60 fallimenti provengono dalla stessa fixture `stripe_env` in `tests/test_r210_operator_refunds.py`,usata anche dai test di recupero e dalle pagine Chromium. Il recente readback Stripe con due acquisizioni coerenti richiede sessione/intent/charge canonici completi;la vecchia simulazione non includeva `livemode`,modalità payment,dati di cattura e cronologia delle charge. La prima verifica la rifiuta correttamente con `ProviderProbeError: Stripe financial environment mismatch`.

Il difetto è riprodotto localmente sulla versione committata,prima della correzione. I blob Git della fixture,di `app/stripe_paid_history.py` e di `app/service_admission.py` coincidono con il cumulativo completo recuperato. Non viene inferita una modifica del comportamento del provider o aggirata una verifica finanziaria.

## Correzione

L'unico file eseguibile modificato è **tests/test_r210_operator_refunds.py**. La fixture fornisce:

- `livemode:false` esplicito e booleano per sessione,intent e charge del merchant test;sessione in modalità payment e intent senza importi ancora catturabili;
- charge riuscita con importi/cattura/riferimenti di bilancio completi,lista delle charge filtrata per l'intent originale e lettura della medesima charge;
- query paginate reali con `limit=100`,refund/dispute filtrati per la charge,e totale rimborsato/flag full-refund coerenti con le ricevute simulate;
- nove rifiuti nel vero servizio di preparazione del rimborso quando ambiente Stripe è errato,assente o non booleano,senza POST al provider,nuovo rimborso o movimento del wallet.

**Tutti i299 file Python di produzione sono identici al cumulativo committato.** Nessun guard livemode,identità,importo,concorrenza,proprietario o conservazione viene allentato. Nessuna dipendenza del progetto,workflow,soglia,scanner,ignore o allowlist viene modificata. I client di pagamento sono simulatori locali;non vengono richiesti rimborsi o effettuate letture di merchant reali.

Il primo adattamento della fixture aveva omesso il parametro di paginazione effettivo `limit=100` nelle asserzioni delle query;è stato corretto. Un nuovo caso negativo sull'ambiente mancante della charge incontrava prima il rifiuto tipizzato di campo incompleto:ora verifica il rifiuto ProviderProbeError e gli invarianti di assenza di effetti,senza vincolare la sicurezza all'ordine delle verifiche. I rapporti iniziali restano conservati;nessuna asserzione originaria è stata rimossa.

## Prove e stato

**156 casi distinti passati,0 fallimenti/errori/skip residui**,compresi **tutti i60 identificativi falliti in CI**,14 casi Chromium reali e9 nuovi controlli negativi. Playwright1.51.0 e Chromium134.0.6998.35 build1161 coincidono con il runtime browser fissato in CI. Le schermate IT/EN390/1280,il rimborso parziale/totale,le perdite di risposta,il recupero dopo morte del processo,la privacy e il wallet vengono verificati con API/SQLite reali e solo trasporto provider simulato.

Provenienza esatta,rapporti e hash: `validation/r210/ci-5891082-result.json`. Gli esiti più recenti dei casi sovrapposti prevalgono;non si sommano le ripetizioni. I gate di sicurezza/trasporto/ammissione sono stati convalidati contro gli stessi299 sorgenti e le revisioni esistenti. La scansione completa SAST positiva del run viene riutilizzata;non serve rieseguire analisi di produzione non modificate. Nessuna nuova Full CI o coverage completa viene dichiarata eseguita localmente.

Stato RC invariato: **25/42(59,5%),0/7 macroaree,PRE-RC**. La correzione di test non promuove un altro criterio. La CI GitHub del prossimo commit deve ancora confermare la correzione;il run40550957081 resta fallito e non è stato rilanciato automaticamente.

## Applicazione

Il cumulativo **MTA-0.3.0-r210-pre-RC-ci-stripe-refund-fixture-cumulative.zip** conserva l'intero package precedente. La patch autonoma **CI_STRIPE_REFUND_FIX_5891082.patch**,in questa directory,modifica soltanto il file di test committato;può essere applicata nella propria copia Git con `git apply` dopo la consueta verifica del diff. La documentazione e il manifest aggiornati sono nel cumulativo. Non distribuire questa correzione di fixture sul server per risolvere un errore runtime:il codice di produzione è invariato.

Per rieseguire il perimetro interessato,con Chromium installato e Playwright1.51.0:

```sh
MTA_TEST_OFFLINE=1 python -m pytest -q tests/test_r210_operator_refunds.py tests/test_r210_operator_refunds_recovery.py tests/test_r210_operator_refunds_ui.py tests/test_r210_account_refund_acceptance.py tests/test_r210_stripe_paid_history.py
```

Non occorre aggiungere `[full-ci]` al prossimo messaggio solo per questa modifica:la regressione mirata comprende già tutti i fallimenti e il browser reale. La CI standard rimane utile per la conferma sul commit;non viene disabilitata alcuna verifica esistente.

Commit suggerito,solo post5891082:

```text
Fix Stripe refund test fixtures for canonical paid history
```

## English handoff

Confirmed commit5891082820d3d69bd8bd3ea0be06117d5639c135 is the new baseline. Full run40550957081 has60 failures sharing an obsolete refund-provider fixture;6818 cases pass and76.78% coverage exceeds70%. SAST/SDK succeed. Complete the fake canonical session/intent/charge environment,capture and charge-list history with real bounded pagination/refund totals. Production correctly refuses incomplete evidence and remains byte-identical across299 Python files. No production guard,workflow,dependency,threshold or scanner is changed.

All60 original failures now pass in a156-case distinct affected union,including14 actual Chromium cases and9 new wrong/missing/nonboolean environment refusals with no dispatch or wallet effect. Exact reports/source evidence are in ci-5891082-result.json. Full CI is not repeated and the next GitHub confirmation is pending. Preserve accepted C2/E5 and all previous cumulative changes;25/42(59.5%) remains PRE-RC. No commit/push/dispatch/provider/server mutation was performed.
