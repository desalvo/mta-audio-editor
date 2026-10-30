# MTA0.3.0-r210 — stato corrente, modello pre-commerciale

**RC v2:32/42=76,2%;D/E complete(2/7);10criteri aperti;PRE-RC.** Il perimetro v1 resta29/42=69,0%,non direttamente comparabile. L'utente ha escluso la migrazione finanziaria commerciale pre-release perché mai attivata. C3/C5/D6 sono ora accettati soltanto sul nuovo profilo iniziale;nessuna migrazione generale è dichiarata completa.

Leggere **PRECOMMERCIAL_MODEL_R210.md**,`validation/r210/precommercial-model/result.json` e `scope-comparison.json`. La cronologia completa precedente è in `development-history/precommercial-scope-20261030/`. Da questo checkpoint le istruzioni storiche che richiedono importazione di pagamenti commerciali mai esistiti sono superate.

Provider/prezzi configurabili prima dell'attivazione;storia monetaria,schemi sconosciuti,intenti e lavori pendenti bloccano. Conservati consumi,saldi,periodi e rendiconti NC. Quote salvate prima del provider,mai ricostruite da prezzi successivi;preventivi non pagati distinti dai pagamenti. Il marcatore d'avvio checkout è immutabile e non personale. Cambio post-checkout automatico non supportato dalla RC semplificata;nessun reset dei libri.

Verifica:894test finanziari/regime finali passati;938casi distinti correnti senza errori o skip,23casi nei nuovi file. Ruff/compilazione/JS,Bandit e tre inventari passano. Nessuna nuova prova browser/provider/target o CI remota.

Base Git confermata:**da300396a8dc9f7b84703565959b4df36dd7c15e**,CI41129584447verde. Tutti i delta merchant-reference più il modello attuale sono non committati. Cumulativo completo:**MTA-0.3.0-r210-pre-RC-precommercial-model-cumulative.zip**. Commit:`Simplify commercial launch, freeze quotes and recover PayPal checkouts`. Nessuna azione remota eseguita.

## Coda residua

1. **A4/A5:** completare gli esiti dei nuovi checkout/rimborsi/dispute,compresi casi parziali/ambigui e recuperi incerti;usare esclusivamente quote e target originali. Non implementare importatori o ricostruzioni finanziarie pre-release.
2. **F4/F6:** completare confini runtime/esecutori e revisioni indipendenti dei checkpoint;non sostituire asset o diritti mancanti con un worker sintetico.
3. **A6/B6/C6/F5/G5/G6:** eseguire i collaudi reali su sandbox,host indipendenti,sistemi installati,container e hardware/modelli autorizzati. C6 mantiene lavoro di integrazione e target;build/skip non equivalgono all'accettazione.

Un blocco funzionale per volta,fino ad accettazione o impedimento concreto. Ogni resoconto riporta il perimetro della percentuale. Non ricontare B2 o i vecchi fix CI. Nessuna mutazione remota o commit automatico.
