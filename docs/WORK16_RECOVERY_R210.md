# Ripresa MTA Work #16 — 30 ottobre 2026

Baseline recuperata: `MTA-0.3.0-r210-pre-RC-independent-guardian-cumulative.zip`, SHA-256 `5a4738d737e15fe2badda0b1b67a2a8307d45035bddbc291b8eed854c3b83524`, 100.485.612 byte e 4.973 percorsi. Versione 0.3.0-r210. Ultimo commit dichiarato `4014a1fd5bfccc4e7f65c32345cb4c52f98f3d8d`; tutti i delta successivi rimangono cumulativi e non committati. Configurazioni, asset e log del cumulativo conservati; nessun intervento sul server o sui provider reali.

## Cosa è stato recuperato e cosa ricostruito

Recuperati archivio e handoff B2, le decisioni della chat #16 e i vincoli di configurazione. La chat riferiva un delta F4 non confezionato con 1.697 test passati e 9 saltati. Il codice di quel vecchio ambiente non è disponibile: quel conteggio resta storico, non prova di questo pacchetto. Non dichiarare recupero integrale o equivalenza byte per byte del delta perso.

Ricostruita una parte verificata di F4: un adapter installato non rende attendibile un eseguibile arbitrario configurato come Python. Gli override per motore, registro e default devono indicare l'interprete della stessa installazione in esecuzione; copie, alias e altri virtualenv non sono attestati dai byte del solo binario. Il controllo avviene nella risoluzione prima di disponibilità/ammissione/ledger e nuovamente nella selezione dell'interprete. L'API token JSON e upload rifiuta l'eseguibile sostituito senza avviarlo né creare job. Un runtime Python esterno impostato esplicitamente richiede ancora un contratto verificabile; rimuovere l'override usa la selezione gestita già esistente, senza certificare automaticamente i suoi import. Nessuna nuova attestazione dei runtime gestiti, upstream, checkpoint o librerie native.

Ripristinata la continuazione finanziaria locale descritta nella chat: uno storico guardian già chiuso, integro e completamente riconciliato non blocca più per la sola presenza delle righe worker. Restano obbligatori verifica di settlement, claim/fence chiusi, scope-count e ricevute originali, audit completo del journal e zero scope pendenti. Storico perdite operatore e provider resta soggetto ai blocchi precedenti. La ricevuta fisica da sola non abilita il cambio di regime. Prove API reali includono lavoro harmony integrato, guardian Linux, passaggio nei due sensi e replay; ricevute mancanti/alterate, journal incompleto, conteggio alterato, operazioni aperte e job incerti sono rifiutati.

## Esiti e limiti

245 casi distinti passati negli esiti più recenti, 52 nuovi, zero failure/skip negli ultimi esiti per identità. Vedere `validation/r210/work16-recovery-result.json`, che conserva report, hash e identità. Non sommare le riesecuzioni. Ruff completo passa; Bandit invariato 307 sorgenti/168 finding (0 HIGH,21 MEDIUM,147 LOW); inventari invariati 554 sorgenti/780 punti runtime,173 confini di ammissione,30 siti HTTP/21 file. Checker, soglie e soppressioni invariati; nessun nuovo finding approvato.

Conservato un errore intermittente del test guardian durante drain: `no such table: worker_cgroup_receipts` nella selezione da245. Il singolo caso e successivamente l'intero file guardian16/16 passano. Causa non stabilita, non dichiarata corretta. Le prime esecuzioni avevano inoltre perso i permessi eseguibili durante il ciclo temporaneo; ripristinati dai metadati ZIP e usata una directory di test separata. Tutti i log diagnostici restano nel pacchetto. Ambiente finale separato con Python3.12, FastAPI0.142.2, Pydantic2.12.5, NumPy2.5.3, pytest9.1.1, Ruff0.16.10 e Bandit1.9.4. Nessuna full CI remota, nuova inferenza neurale o prova installata Windows/macOS/GPU.

## Avanzamento e prossima ripresa

**PRE-RC 29/42 = 69,0%, invariato.** Questa metrica conta i criteri RC originali, non tutte le funzionalità del prodotto; la percentuale globale del prodotto non è misurata. E rimane la sola macroarea accettata. Non promuovere F4 per questa ricostruzione parziale.

Restano A4,A5,A6,B6,C3,C5,C6,D6,F4,F5,F6,G5,G6. Proseguire F4 sui contratti dei runtime gestiti/import/dipendenze virtualenv, root upstream Mega53/DiffSinger, checkpoint e native dinamiche; poi finanza generale/legacy C3/C5/D6. Il rifiuto di eseguibili opachi e B2 sono già implementati: non ripeterli per gonfiare il conteggio. Monitorare il test intermittente guardian/drain. B6 e i collaudi target mantengono i requisiti originali.

Nessun commit/staging/push/tag, dispatch CI o intervento di produzione eseguito. Commit suggerito cumulativo dopo4014a1f:

`Enforce model rights, recover crashed workers and preserve verified guardian history`

Cumulativo autosufficiente: `MTA-0.3.0-r210-pre-RC-work16-recovery-cumulative.zip`. Leggere prima questo documento, poi DEVELOPMENT_STATUS.md e DEVELOPMENT_COMPONENTS_R210.json; i checkpoint storici successivi nel testo non prevalgono su questa ripresa.
