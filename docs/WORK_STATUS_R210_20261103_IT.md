# Stato di lavoro verso la RC — 3 novembre 2026

Questa consegna non dichiara una release candidate. Il conteggio precedente riportava 34 criteri chiusi su 42 (81%); la nuova specifica introduce sette macroaree per il benchmark percussioni. Come stima di lavoro non ponderata, 36/49 = 73% considera concluse localmente la dismissione SAM e l'interfaccia di valutazione. La stima non sostituisce i controlli di rilascio e non considera accettata alcuna prova non eseguita. Le nuove funzioni di collaborazione richiedono ancora accettazione in ambiente multiutente reale.

- Timeline e lyrics: 11/11 requisiti implementativi locali; verifiche automatiche, PCM, archivio, undo/redo e autenticazione endpoint. Restano prove visive in browser e applicazioni native.
- Collaborazione: componenti implementati e testati localmente, inclusi messaggi, allegati, scadenze, notifiche, gestione condivisioni, revisioni e protezione undo/redo. Restano accettazione multi-browser/proxy, microfono e SMTP reale; nessuna azione su server di produzione.
- Corpus: 18/24 casi preparati (12 sintetici e 6 difficili); 6 casi reali mancanti. I 36 controlli su riferimenti esatti non sono inferenze di modelli.
- Modelli candidati: 1 adapter eseguibile su 11 elencati; pesi non inclusi, altre integrazioni e diritti da verificare. Nessun modello neurale reale eseguito e nessun vincitore scelto.
- Benchmark: API, interfaccia di ascolto, metriche, protezione archivi e consenso esplicito implementati e verificati con fixture. La validazione professionale richiede inferenze reali, almeno sei famiglie di registrazioni reali distinte e consenso umano. I contatori CPU/GPU/RAM/VRAM non sono ancora acquisiti nel report: sono nulli e non sono stime.
- Una campagna importata mantiene lo storico ma non eredita approvazioni; per rieseguirla occorre registrare il corpus originale con gli stessi hash.
- La full CI remota 41562792488 ha rilevato cinque test non aggiornati e cinque falsi positivi del controllo segreti; il fix locale è documentato in `docs/CI_41562792488_REVIEW_R210_IT.md` e attende una nuova full CI. SMTP, microfoni e accettazione reale multiutente non sono stati verificati. Le percentuali descrivono stato locale e non attestano la sicurezza o la prontezza della release.

Per applicare il cumulativo a un checkout esistente, vedere `docs/APPLY_CUMULATIVE_20261103_IT.md` e `DELETED_FILES_R210.txt`.
