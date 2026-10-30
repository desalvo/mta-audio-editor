# Legacy subscription collection — MTA 0.3.0-r210 — 30 ottobre 2026

**RC: 69,0% (29/42 criteri originali), invariata. Nessun criterio promosso; 13 aperti, E completa (1/7). L'aumento percentuale richiesto non è ancora ottenuto.**

Corretto un difetto riprodotto sul codice precedente: un rimborso autenticato di un abbonamento legacy privo della base originale poteva generare un nuovo credito da riscuotere sottraendo il saldo rimborsabile mutabile. Anche un credito legacy già registrato poteva avviare un nuovo pagamento senza più la prova della quota originale. Quattro casi iniziali fallivano; i log sono conservati.

## Comportamento risultante

- Il rimborso canonico resta registrato una sola volta nel ledger finanziario, anche con eventi concorrenti. Senza base originale non viene creato un credito da riscuotere, neppure di importo zero, e il saldo storico rimborsabile dell'abbonamento non viene ricostruito.
- Con una base originale valida, quota, surplus residuo e tetto delle obbligazioni dipendono da quella base e dai movimenti effettivi; una variazione del saldo rimborsabile corrente non cambia la quota recuperabile. Il preventivo di rimborso/recupero viene ricontrollato prima della capture dopo la rilettura di approvazione.
- I crediti legacy esistenti, le allocazioni e i pagamenti rimangono conservati. Mancanza/conflitto della base, proprietario/periodo diversi, capture incomplete, finanziamento non provato o allocazioni oltre la perdita originale sospendono la riscossione. Importi da recuperare, regolati e rimborsi dipendenti da copertura ignota sono null/da verificare, mai uno zero o una quietanza inventati.
- Il rifiuto avviene prima di un nuovo POST al provider e anche nell'allocazione finale. Un pagamento già completato esternamente senza prova originale non riceve un'allocazione inventata; il completamento applicativo viene rifiutato e l'operazione originale resta da riconciliare. Non vengono eseguite nuove capture, liberazioni del fence o cancellazioni per risolvere l'incertezza.
- L'account mostra un avviso IT/EN e sospende l'azione di pagamento del credito non verificato; il resto della vista rimane consultabile. La revisione delle prove è limitata al proprietario e non espone le anomalie di altri account. L'aggregato amministrativo sconosciuto è null e conserva il blocco di riconciliazione/cambio di regime.
- Ripristinando l'esatta prova originale conservata, lo stesso checkout approvato torna verificabile e si regola una sola volta. Il test usa una copia sintetica esatta della base originale; non dimostra la presenza di una prova storica reale né consegna una migrazione automatica.

## Verifica corrente

**779 casi distinti interessati passati, 24 nuovi; 10 saltati per Playwright assente; nessun fallimento/errore corrente.** L'esito usa l'unione degli ultimi risultati per identità, non la somma delle riesecuzioni. La regressione ampia precedente al controllo finale passa 777 casi con 10 skip; il controllo finale copre anche privacy su un legame legacy errato e ripresa dell'esatto pagamento originale. Prova dettagliata: `validation/r210/legacy-collection-result.json`.

API FastAPI/SQLite reali, trasporto provider simulato: nessun sandbox o conto reale contattato. Quattro scenari eseguono le funzioni del JavaScript distribuito in Node per IT/EN, con e senza credito preesistente; non sono Chromium né accettazione dell'intera UI. Nessuna nuova prova native/GPU/modelli o full CI. Le prove accettate sui confini invariati rimangono conservate.

Ruff completo app/native/tests/scripts, compilazione dei Python modificati e sintassi JavaScript passano. Gate di sicurezza/inventari passano con checker e soglie invariati:308 sorgenti app,168 finding già revisionati (0 HIGH/21 MEDIUM/147 LOW),nessun finding nuovo o soppressione;runtime555 sorgenti/780 confini,C2 173 siti,HTTP30 siti/21 file. Le chiamate censite restano identiche,sono aggiornati i vincoli ai byte dei sorgenti modificati.

## Impedimenti e prossima azione

A5/C3 restano aperti: la prova storica indipendente di quota/surplus dei pagamenti legacy non è disponibile e il percorso di migrazione completa verificata resta da implementare su un contratto probatorio effettivo. Prezzi attuali, solo lordo del provider e saldi modificabili non sono sostituti. Il blocco ora impedisce la riscossione, ma non ricostruisce il passato e non equivale a chiusura del criterio originale.

A4 mantiene lavoro software e prove mancanti per storia completa del conto, riferimenti originali e altri movimenti/formati/stati payout/protection. Non ripetere collector, audit di copertura o allocazione parziale già consegnati. Procedere sul prossimo scenario non coperto con prova canonica sufficiente; registrare il documento/legame preciso quando manca. C3/C5/D6 non si abilitano per effetto di questa correzione. F4/F6 rimangono una coda indipendente con contratti residui e modelli/runtime/diritti effettivi, senza ripetere i test MT3 o ACE UI già chiusi.

I criteri target A6/B6/C6/F5/G5/G6 mantengono le prove effettive richieste. Non tutti i residui sono esterni. Ogni resoconto continua a riportare percentuale RC e verificati/42; nessun criterio, peso o denominatore modificato.

## Ripresa autosufficiente

Unico cumulativo completo: `MTA-0.3.0-r210-pre-RC-legacy-collection-cumulative.zip`. Include l'ultimo ACE cumulative (SHA256 `ff08b5549904981ffb1950c87987feabb6bfa6fd1d6490e3e2af73614cf860f0`), il delta di riorganizzazione e tutte le modifiche successive non committate da `4014a1fd5bfccc4e7f65c32345cb4c52f98f3d8d`. Estrarre questo archivio: non riapplicare il vecchio delta documentale. Sorgenti,legacy AI,VST,asset,licenze,manuali e log storici sono conservati con i metadati originali delle voci ZIP.

Nessun commit/staging/push/tag/release,dispatch CI o intervento reale server/provider eseguito. Versione0.3.0-r210 invariata;PRE-RC e cambio generale disabilitato. Dopo il commit dell'utente verificare Quality/SAST ordinari;nessun nuovo opt-in richiesto dalle prove unit aggiunte.

Commit cumulativo suggerito:

`Enforce model rights, recover workers, isolate ACE observers and verify subscription debt`
