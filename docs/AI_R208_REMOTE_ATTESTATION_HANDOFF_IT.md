# R208 – Contratto di attestazione remota

## Sviluppo implementato

Il client remoto può ora richiedere obbligatoriamente **entrambi** gli header
`X-MTA-AI-Request-ID` e `X-MTA-AI-Result-SHA256`, verificati sui byte restituiti
prima di considerarli un risultato valido. La regola vale sia per POST sia
per GET di recovery, compreso il recupero automatico dopo errore di rete.

Per l'installazione nativa configurare `MTA_REMOTE_AI_REQUIRE_ATTESTATION=1`
per non accettare risultati da server legacy che non espongono le attestazioni.
La modalità predefinita mantiene la compatibilità con vecchi server, ma continua
a rifiutare attestazioni presenti e non valide.

Questo controllo verifica l'integrità e il legame richiesta-risultato, **non**
l'attendibilità dei dati GPU: telemetria, attribuzione per job, raccolta da
worker e certificazione EL10/ROCm restano attività distinte.
