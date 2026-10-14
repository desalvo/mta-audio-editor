# MTA 0.3.0-r208 — diagnostica e coordinamento job AI

## Modifiche incluse
- Pagina Amministrazione > Diagnostica: attivazione opt-in e download ZIP autenticato.
- ZIP a scadenza 24h; pulizia periodica oraria e limite di 12 archivi.
- Dati strutturati limitati e sanitizzati; gli eventi di log includono solo metadati (senza messaggi, body, prompt, token, env, traceback).
- Coda transazionale condivisa con AI Arranger/Remix web, estrazione lyrics/chords, separazione stem, download modelli.
- Le risposte dei job legacy includono posizione in coda e numero di job davanti.
- install_mta.sh: --no-wizard esegue configurazione unattended; --configure-only mantiene il wizard; riconciliazione worker in setup non interattivo.

## Limitazioni aperte — non certificare come completate
- Tutti gli altri adapter/endpoint AI nativi e remoti devono essere migrati, testati e coordinati.
- Non è ancora disponibile l'arresto forzato affidabile per i job GPU in esecuzione.
- La coda salva i metadati in SQLite ma NON persiste/replay automaticamente le closure di esecuzione tra riavvii.
- I secondi GPU per job restano N/A finché non c'è telemetria attendibile.
- La diagnostica non esporta log grezzi né contenuto dei progetti; servono eventi diagnostici strutturati aggiuntivi nei worker.
- Non sono stati eseguiti test su EL10 né inference reali; necessario collaudo e Quality completa.

## Note sicurezza
- Diagnostica spenta per default, accessibile solo admin, file mode 0600, directory 0700.
- Eventi privi di messaggi originali per minimizzare i dati sensibili.
- Non esporre directory temporanea attraverso static files.
