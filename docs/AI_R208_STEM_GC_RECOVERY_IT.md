# MTA Audio Editor 0.3.0-r208 — Stem GC e recovery

## Interventi
- Durante lo staging di ciascuno stem viene registrato il WAV di destinazione prima della copia e l'eventuale nuovo nome dopo la normalizzazione. Gli errori di staging non lasciano più i WAV iniziali non censiti dal rollback logico.
- Gli audio delle tracce sostituite non vengono più rimossi direttamente nel thread di pubblicazione. Dopo il salvataggio atomico del progetto vengono consegnati alla coda di garbage collection durevole già presente nello storage.
- In caso di errore prima della pubblicazione, i file preparati sono inseriti nella stessa coda. Prima di cancellare, il GC rilegge `project.json` ed esclude ogni file ancora referenziato.
- Il servizio startup esistente invoca `resume_pending_gc`, che riscopre i file orfani e riprende le cancellazioni non concluse dopo un crash.

## Verifiche
- 234 test r208 superati.
- 243 test inclusi workflow stem, selective stems e native stem superati.
- Compilazione Python e sintassi `scripts/install_mta.sh` superate.

## Limiti
- L'esecuzione di `save_project` in FLAC può richiedere una migrazione dell'intero progetto; questa modifica ne protegge la pulizia dei residui, ma non certifica una transazione distribuita perfetta fra file e DB.
- Lo scheduler AI remoto, il metering GPU attendibile per job e l'inferenza reale su Rocky EL10/ROCm necessitano ancora completamento/verifiche.
- La pulizia è asincrona; in caso di problemi permanenti di permessi su disco gli orfani possono richiedere manutenzione.
