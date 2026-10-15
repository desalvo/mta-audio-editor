# MTA 0.3.0-r208 — certificazione locale adapter e billing (13 ottobre 2026)

## Ambito verificato
- 46 test mirati: adapter gateway/unificati, concorrenza, recupero job, billing transaction, atomic close e reconciliation: superati.
- 131 test r208 e principali regressioni transazionali billing: superati.
- `terminal_receipts` aggiunto nella SQLite della coda AI: l'inserimento della ricevuta finale avviene nella stessa transazione che aggiorna lo stato del job, con `job_id` chiave primaria e `INSERT OR IGNORE`. Copre completed/failed/cancelled/interrupted.
- Job avviati prima della modifica non sono retrocompilati automaticamente con ricevute terminali: evitare di inferire storici non verificati.

## Limitazioni e condizioni non certificate
- La ricevuta della coda NON è un addebito. Il database del ledger di fatturazione è separato: non esiste in questo intervento una transazione distribuita per pubblicazione progetto, ricevuta queue e ledger billing.
- La presenza di test per Whisper, Demucs, DrumSep, SAM Audio, singer separation, chords e ACE-Step non certifica tutti i backend reali: la certificazione end-to-end richiede modello, runtime, endpoint reale e misurazione hardware sul server EL10/ROCm 7.2.4.
- Non dichiarare certificazione completa del billing exactly-once, cancellazione remota universale o metering GPU senza evidenza di collaudi hardware e collegamento tra i sistemi.
- Gli ingressi legacy `_enqueue_existing_ai_job` ancora dipendono da callback in memoria e non sono recuperabili universalmente dopo reboot.

## Verifiche da eseguire su hardware prima della certificazione di produzione
1. Riavvio servizio mentre sono presenti job in attesa e durante inferenza; esaminare ripristino e stato `interrupted` senza output duplicati.
2. Verificare per ciascun adapter: submit, progress, timeout, cancel locale/remoto, risultato, assenza di doppie pubblicazioni dopo retry.
3. Verificare in ledger il legame a chiave univoca del job, snapshot misurati di CPU/GPU e comportamento in presenza di crash tra pubblicazione e contabilizzazione.
4. Verificare credenziali sanitizzate negli archivi diagnostici e modalità installer `--configure-only` / `--no-wizard`.
