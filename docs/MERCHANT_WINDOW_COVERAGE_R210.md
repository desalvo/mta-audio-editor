# MTA r210 — Copertura temporale merchant

28 ottobre 2026, Europe/Rome. PRE-RC, 28/42 (66,7%), E completa 1/7. Nessun criterio promosso: aumento percentuale richiesto non ancora raggiunto. Commit differito; nessuna azione GitHub o server/provider reale.

Ripristinato il cumulativo merchant-ledger SHA ccdd96865352b1234474d8b567b15b275bc42ca058553fb6b3bd822d6a445c12: 4651 file, CRC e manifest verificati. Tutto il delta B5/drain/E4/F3/merchant è conservato.

Nuovo strumento offline `scripts/audit_merchant_coverage.py`: apre SQLite con mode=ro e query_only, verifica identità, digest e DTO di ogni snapshot prima di filtrare merchant/ambiente, unisce finestre adiacenti/sovrapposte e riporta i vuoti esatti. Snapshot discordanti della stessa finestra impediscono il risultato coperto. I riferimenti delle prove e un digest deterministico rendono il risultato ripetibile. Database mancante/corrotto: errore, nessun file creato e nessun risultato vuoto dichiarato sicuro.

Uso su una copia coerente del database, mantenendo i journal SQLite necessari:

```bash
python scripts/audit_merchant_coverage.py --database /percorso/copia.db --start 2026-09-01T00:00:00Z --end 2026-09-05T00:00:00Z --environment sandbox --fingerprint SHA256_DEL_CLIENT_ID
```

Non passare segreti o client ID: il fingerprint è il digest merchant già presente negli snapshot. Codici uscita: 0 intervallo richiesto coperto dalle osservazioni persistite; 2 vuoti/conflitti; 1 audit indisponibile/input invalido. Nessuna rete o modifica al ledger. Il risultato non prova freschezza, origine della vita del conto, disponibilità dello storico remoto, coerenza economica di finestre diverse o settlement. I flag complete_account_history,ledger_reconciled,transition_authorized,release_candidate restano falsi. Nessun collegamento a readiness/cutover e nessuna deroga ai blocchi esistenti.

Tredici nuovi test verificano intervalli vuoti, adiacenti, sovrapposti, lacune iniziali/finali/interne, conti/ambienti diversi, corruzione non nascosta dal filtro, conflitti e CLI read-only con confronto dei byte del database. Gate di inventario runtime rieseguito solo perché è stato aggiunto uno script: 543 sorgenti,782 punti invariati. Codice app, UI e prove precedenti non modificati; Bandit/F3/Chromium/full CI invariati conservati. Report esatto: validation/r210/merchant-window-coverage.xml; riepilogo merchant-window-result.json.

Restano 14 criteri originali: A4,A5,B2,C3,C5,C6,D6,F4,F6 e cinque target A6,B6,F5,G5,G6. Prossimo blocco: acquisizione e continuità merchant integrate, riferimenti locali mancanti e allocazione payout/protection con prova originale; poi basi legacy quota/surplus. Non dichiarare completo A4/C3 dalla sola unione di intervalli. Il bridge API/UI precedente resta il percorso originale di recupero.

Cumulativo unico: MTA-0.3.0-r210-pre-RC-merchant-coverage-cumulative.zip. Conservati tutti i percorsi, log originali, asset, licenze, manuali e metadati ZIP. Nessun runtime/browser incluso.

Commit cumulativo suggerito, non eseguito: `Complete guarded execution, administration and merchant history recovery`
