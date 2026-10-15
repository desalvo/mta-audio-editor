# R208 — Integrità del risultato remoto e finalizzazione

- Il risultato del worker è validato prima di salvare la cache e confermare il completamento della richiesta idempotente, su entrambi gli ingressi JSON e WAV.
- Il contratto verifica tipo bytes, non-vuoto, limite 32 MiB, identificativo del job e tipo MIME consentito.
- Risultati non validi dopo l'esecuzione sono marcati failed nella deduplicazione: non verranno rieseguiti automaticamente, e il billing già acquisito non viene ignorato.
- Gli upload WAV con Content-Length presente sono rifiutati se la lunghezza ricevuta non coincide; rifiutato l'override di `kind` discordante nelle opzioni.
- Suite r208: 256 test superati. La certificazione con worker GPU reali e l'attribuzione GPU sono ancora aperte.
