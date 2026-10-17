# Validazione r210 — Centro job AI

Data: 2026-10-17 UTC. Versione 0.3.0-r210 invariata.
Base completa: MTA-r210-ace-cold-start.zip, 1444 file,
SHA-256 849b75353406f08657f8df1e6053d70e3b78ef603dcb8366341ce630eac73c4f.
Ultimo commit utente verificato su GitHub:
6fd5d6f25523aaed20c8b37d0ae3a69e08c608bf
(Fix ACE cold-start retries without cancelling accepted generation tasks).
Nessun commit, push, tag, release o intervento sul server eseguito dall'assistente.

## Modifiche

Centro job indipendente dal progetto/modal con cronologia paginata, badge dei
job attivi, azioni singole/multiple, selezione per intervallo, ultimi N o tutti,
ACL di progetto, protezione CSRF e inbox notifiche persistente per account.
Rimozione operativa per account: coda e contabilità sono conservate; gli attivi
non sono archiviabili. Annullamento solo tramite i controlli confermati esistenti.
Notifiche interne e browser opzionali, recupero alla riconnessione, aggiornamento
del progetto corrente. La pagina MTA deve restare aperta per gli avvisi live.

Arranger a tre schede con opzioni a scorrimento limitato, CPU/GPU/elapsed grandi
e qualificazione delle fonti. Corretto il messaggio terminale di annullamento.
Progresso ACE autenticato: fasi e forward DiT osservati sul percorso Turbo/Euler
supportato; percentuale complessiva esplicitamente stimata e limitata sotto 100
prima della pubblicazione MTA. Fallback per backend non aggiornati/altre modalità.

Billing: collegamento Settings e redirect admin protetto; corretto un selettore
DOM che interrompeva il caricamento iniziale. Token AI ridisegnato con navigazione,
utenti attivi, ricerca/stato, date, copia segreto mostrato una sola volta,
rotazione/revoca e header CSRF. Nessun segreto salvato nel browser dal nuovo codice.

Nessuna promozione del profiler GPU a consumo fatturabile. Nessuna modifica alle
regole di metering, cgroup, sicurezza, accounting, opt-in o tariffe. La barra non
è un contatore di consumo. I limiti hardware e le prove mancanti sono descritti
in AI_JOB_CENTER_R210.md.

## Esiti

- Regressione completa finale: **3364 passed, 4 skipped, 10 deselected**;
  durata 207.78s (0:03:27). Zero failure/error, JUnit incluso.
- Copertura app: **74.78%**, soglia70 superata.
- Controlli mirati finali: **115 passed**, JUnit incluso.
- Nuovi casi di test: 32 (backend storico/notifiche/pagine/progresso e JS reale).
- Ruff app/native/tests/scripts/k8s-wizard.py: superato.
- Node --check: app.js, admin.js, ai_jobs.js, ai_tokens.js e script inline Billing,
  tutti superati; log incluso.
- Rendering statico della pagina Token AI controllato internamente. Non equivale
  a una prova interattiva nel browser Windows/server; nessuno screenshot privato
  è incluso nell'archivio.
- ZIP cumulativo: tutti i 1444 file di base conservati, nuovi sorgenti/test/documenti
  aggiunti esplicitamente, verifica CRC e SHA-256 del file finale.

Copertura mirata: accesso anonimo negato, admin e proprietario di progetto,
progetto estraneo escluso, CSRF, selezioni singole/date/numero/tutti, ricevute
immutate, isolamento account, archiviazione attivi impedita, cancellazione coda,
paginazione e contatore attivi indipendente dai filtri. Inbox senza vecchi avvisi
al primo accesso, completamento dopo la chiusura UI, acknowledgement persistente,
deduplicazione e filtri che non sopprimono gli avvisi. Esecuzione del JavaScript
monitor con DOM/HTTP isolati e del renderer Arranger reale con stato cancelled
che conserva cancel_requested. Campi presenti in tutte le schede e strumenti
nativi assenti dal markup server. Endpoint ACE autenticato, callback preservato
una volta, hook nel thread proprietario con rimozione, fallback modalità ignote,
overflow valutazioni invalidato, telemetria malformata/estranea scartata.
Restano inclusi i test precedenti di annullamento, timeout lungo, cold start,
misure GPU diagnostiche, accounting e pubblicazione.

## Risultati intermedi e ambiente

Il primo passaggio, avviato durante lo sviluppo, ha trovato 4 failure su 3332 casi.
I log/XML iniziali sono conservati. Il conteggio delle richieste nel vecchio
mock ACE è stato aggiornato per il nuovo GET opzionale; le fixture JS sono state
aggiornate per il nuovo testo e per elementi DOM distinti dei contatori. La prova
GC aveva una race con daemon di suite precedenti mentre pdir/load_project erano
sostituiti globalmente: il test ora attende i worker GC preesistenti prima del
mock, senza modificare la protezione dei file di produzione o le asserzioni.
Il rerun dei 27 casi correlati passa. Un secondo passaggio completo ha trovato due fixture JS precedenti senza i globali browser URLSearchParams/location e document richiesti da navigazione job e schede; sono state completate e il ripristino del progetto è ora verificato anche con il parametro ai_project. Log/XML di questo passaggio sono inclusi come integration. Una fixture DOM nuova è stata completata
per rappresentare correttamente l'attributo hidden; la prova finale del monitor
esegue con successo lo script di produzione a lista chiusa.

I 4 skip riguardano SDK Steinberg/ADelay opzionali assenti. I 10 casi esclusi
sono integrazioni AF_UNIX non disponibili nel runner, con la stessa selezione
esplicita del ciclo precedente; non sono dichiarati superati. I warning sono
conservati nei log. Il runner non dispone di AMD/ROCm né del browser/dispositivo
di produzione: nessuna inferenza hardware reale nuova o build RPM installata
sul server è stata eseguita dall'assistente.

## Collaudo ancora richiesto

L'utente conferma generazione breve, annullamento, profilazione e superamento
600s sulla base precedente. Restano da provare sul nuovo RPM: nuova UI, messaggi,
job in background/notifiche, filtri/rimozioni con account diversi, endpoint di
progresso dopo riavvio ACE a coda vuota, generazione lunga fino a conclusione e
playback/persistenza del risultato. Verificare anche il download ZIP diagnostico.
Non viene dichiarata la certificazione completa del server né il billing GPU.
