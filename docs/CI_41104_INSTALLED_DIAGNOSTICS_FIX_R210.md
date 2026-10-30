# MTA 0.3.0-r210 — correzione CI41104088648

**RC 69,0% (29/42), invariata; nessun criterio originale promosso.**

Il commit utente `2273dc4f6a797a09ae2762b3545ed351c6111e74` è la baseline corrente: tutti i 4315 blob tracciati coincidono con il cumulativo CI41098 recuperato prima delle modifiche. Il precedente hotfix Gitleaks è quindi committato e confermato dal nuovo job SAST riuscito, incluso Trivy.

## Errore osservato

Il secondo tentativo della run41104088648 fallisce nel job Quality124272437758: un solo errore, `test_windows_installed_executable_without_powershell`, termina dopo il timeout esterno di25secondi. Passano7682test,50sono saltati;copertura76,57%,soglia70%. VST3 SDK e SAST riescono;10job dipendenti sono saltati. Il primo tentativo aveva Quality riuscito, con cancellazioni macOSarm64/iOS: non viene dichiarato riuscito l'intero workflow.

La diagnostica cercava PowerShell anche su Linux, dove è installabile ma la verifica Authenticode di Windows non è supportata. L'output si ferma dopo `executable_signature`,prima del risultato Authenticode. Il comando interno aveva lo stesso timeout25s dell'intero processo nel test: un avvio lento può quindi esaurire il limite esterno prima della scrittura del report.

## Correzione

`scripts/installed_diagnostics_r208.py` esegue Authenticode soltanto su host Windows. L'ispezione su un altro sistema conserva i controlli statici ed emette `authenticode: SKIP` con motivo esplicito. Su Windows restano il comando statico, il pathname passato tramite ambiente, il timeout25s e il ripristino dell'ambiente.

Il test già esistente senza PowerShell ora isola realmente PATH. Quattro nuovi casi verificano entrambe le denominazioni pwsh/powershell su host estraneo senza avviare il processo e conservano esito valido/timeout della verifica Windows. Non sono stati aumentati timeout, disabilitati test o modificati workflow/dipendenze. La revisione inventario è aggiornata soltanto per il sorgente diagnostico modificato e la prova corrispondente.

## Verifica e consegna

- Sorgente originale con regressioni attuali:2fallimenti riprodotti,6passati.
- Dopo il fix:31passati,0fallimenti,0skip su diagnostica, sicurezza input e inventario/esecuzione AI;Python3.12 locale.
- Ruff e compilazione Python passano.
- Tre gate inventario passano:555sorgenti/780confini esecutivi,308sorgenti/173siti ammissione,21sorgenti/30trasporti. Checker e soglie invariati.
- La nuova CI Python3.14 e Authenticode reale su Windows restano da verificare dopo il commit;nessun nuovo full-CI o criterio target dichiarato.

Cumulativo completo: **MTA-0.3.0-r210-pre-RC-ci-41104-cumulative.zip**. Include tutti i delta precedenti,asset,licenze,log e metadati originali dello ZIP. Prove in `docs/validation/r210/ci-41104/`.

Commit suggerito: `Run installed Authenticode diagnostics only on Windows`

Solo questo fix,test,revisione e stato sono successivi al commit2273dc4;nessun commit/push/tag/dispatchCI,rilascio o intervento server/provider eseguito. Restano13criteri originali aperti;la correzione CI non modifica il conteggio RC.
