# MTA0.3.0-r210 — stato corrente, modello pre-commerciale

**RC v2:32/42=76,2%;D/E complete(2/7);10criteri aperti;PRE-RC.** Il perimetro v1 resta29/42=69,0%,non direttamente comparabile. L'utente ha escluso la migrazione finanziaria commerciale pre-release perché mai attivata. C3/C5/D6 sono ora accettati soltanto sul nuovo profilo iniziale;nessuna migrazione generale è dichiarata completa.

Leggere **PRECOMMERCIAL_MODEL_R210.md**,`validation/r210/precommercial-model/result.json` e `scope-comparison.json`. La cronologia completa precedente è in `development-history/precommercial-scope-20261030/`. Da questo checkpoint le istruzioni storiche che richiedono importazione di pagamenti commerciali mai esistiti sono superate.

Provider/prezzi configurabili prima dell'attivazione;storia monetaria,schemi sconosciuti,intenti e lavori pendenti bloccano. Conservati consumi,saldi,periodi e rendiconti NC. Quote salvate prima del provider,mai ricostruite da prezzi successivi;preventivi non pagati distinti dai pagamenti. Il marcatore d'avvio checkout è immutabile e non personale. Cambio post-checkout automatico non supportato dalla RC semplificata;nessun reset dei libri.

Verifica:894test finanziari/regime finali passati;938casi distinti correnti senza errori o skip,23casi nei nuovi file. Ruff/compilazione/JS,Bandit e tre inventari passano. Nessuna nuova prova browser/provider/target o CI remota.

Base Git: **ee4e37fd30c39a72638b303b01ca0cd5b090f272**, full CI 41156985339 verde. Delta non committati: recupero checkout, quote, piano RC, ricerca rimborsi incerti Stripe e PayPal e rilettura limitata per race del registro Stripe. **358 test passati, 16 browser saltati**, più 4 test mirati di cui 2 nuovi; provider reali e nuova CI non verificati. Ruff, SAST e inventari passati. Il criterio A5 e il batch richiesto di 20 cicli restano aperti. Dettagli `PAYMENT_REFUND_RECOVERY_BATCH_R210.md`. RC invariata **32/42=76,2%**. Commit: `Recover uncertain refunds across providers and harden checkout`.

## Recupero pagamenti completati — ultimo batch

Il recupero proprietario PayPal usa ora lo storico autenticato anche se le condizioni di acquisto cambiano dopo l’acquisizione; storia incompleta e segnalazioni concorrenti bloccano l’accredito. Le ripetizioni terminali Stripe/PayPal conservano la ricevuta originale; una rata eccedente già acquisita genera un rimborso dovuto. Suite finale: **461 passati, nessuno skip**, provider simulati; Ruff, SAST e inventari passati. La suite intermedia aveva un fallimento corretto e verificato. Nessuna nuova CI o prova provider/browser. Dettagli: `PAYMENT_COMPLETED_RECOVERY_R210.md`. **RC invariata 32/42=76,2%**; A4/A5 e il batch di 20 cicli restano aperti. Commit cumulativo: `Recover uncertain payments and refunds across providers`.

## Prima contabilizzazione Stripe e PayPal

Le prime notifiche pagate riconciliano lo storico autenticato prima di rendere disponibili i crediti; Stripe recupera anche il riferimento perso e conserva il webhook nella transazione. Per PayPal un blocco di epoca non produce un falso gap prima della lettura. I webhook non bloccano l’event loop. Verifiche: 577 passati prima dell’ultimo aggiustamento, poi suite interessate 238 e 26 passati, 22 browser saltati; 10 casi Stripe finali passati. Le suite si sovrappongono. Nessuna nuova CI o prova provider reale. Dettagli e limiti: `PAYMENT_FIRST_FUNDING_R210.md`. **RC 32/42=76,2%**; A4/A5 e il batch di 20 cicli restano aperti. Commit cumulativo: `Reconcile initial payments and uncertain refunds across providers`.

## Coda residua

1. **A4/A5:** completare gli esiti dei nuovi checkout/rimborsi/dispute,compresi casi parziali/ambigui e recuperi incerti;usare esclusivamente quote e target originali. Non implementare importatori o ricostruzioni finanziarie pre-release.
2. **F4/F6:** completare confini runtime/esecutori e revisioni indipendenti dei checkpoint;non sostituire asset o diritti mancanti con un worker sintetico.
3. **A6/B6/C6/F5/G5/G6:** eseguire i collaudi reali su sandbox,host indipendenti,sistemi installati,container e hardware/modelli autorizzati. C6 mantiene lavoro di integrazione e target;build/skip non equivalgono all'accettazione.

Un blocco funzionale per volta,fino ad accettazione o impedimento concreto. Ogni resoconto riporta il perimetro della percentuale. Non ricontare B2 o i vecchi fix CI. Nessuna mutazione remota o commit automatico.
