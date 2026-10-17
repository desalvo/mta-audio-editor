# r210 — Centro job AI, Arranger e amministrazione

Versione **0.3.0-r210**, invariata. Archivio cumulativo basato su
`MTA-r210-ace-cold-start.zip` (SHA-256
`849b75353406f08657f8df1e6053d70e3b78ef603dcb8366341ce630eac73c4f`).
Ultimo commit utente verificato: `6fd5d6f25523aaed20c8b37d0ae3a69e08c608bf`
(`Fix ACE cold-start retries without cancelling accepted generation tasks`).
L'assistente non ha effettuato commit, push, tag, release o modifiche al server.

## Centro job AI

Il pulsante fisso **Job AI** è disponibile nell'editor, in Settings, AI Billing
e Token AI. Il controllo dello stato continua con Arranger e lista chiusi,
indipendentemente dal progetto visualizzato. La lista mostra i job della coda
condivisa per i progetti accessibili all'account; l'amministratore vede tutti.
Comprende stato effettivo, avanzamento disponibile, CPU/GPU, elapsed, accesso al
progetto e annullamento. La cronologia è paginata (100 righe per pagina).
Il badge dei job attivi resta globale anche filtrando la cronologia.

Operazioni singole o multiple:

- job selezionati, anche su più pagine;
- intervallo di **creazione** con orario locale: inizio incluso, fine esclusa;
- ultimi N job compatibili (1–5000), dal più recente;
- tutti i job compatibili, elaborati in lotti da 5000.

I filtri di stato si applicano alle operazioni per intervallo, numero e tutti.
La selezione esplicita usa i job spuntati. Una preview conta i job compatibili
prima della conferma. Un annullamento attivo resta una richiesta fino all'uscita
confermata del worker. I worker senza supporto all'annullamento confermato sono
segnalati; non vengono terminati forzatamente dal nuovo centro.

**Rimuovi dalla lista** riguarda soltanto i job terminati e la cronologia di
questo account. Non elimina l'audio del progetto, i record della coda, le ricevute
terminali, i ledger, le pubblicazioni/outbox o le fatture. Gli altri account
conservano la propria vista. I job attivi vanno prima annullati o conclusi.
Non è una funzione di cancellazione dei dati contabili.

## Notifiche e lavoro in background

Un controllo periodico ogni circa 5 secondi produce avvisi di completamento,
fallimento, annullamento o interruzione anche con lista e Arranger chiusi.
L'inbox e le conferme di lettura sono persistenti; al primo accesso non vengono
riproposti tutti i vecchi job. I filtri e la paginazione non sopprimono gli
avvisi. La deduplicazione locale evita di ripetere lo stesso avviso dopo una
riconnessione. L'avviso offre **Apri progetto**. Nell'editor il progetto corrente
viene aggiornato al completamento, se ancora quello aperto alla richiesta.

La pagina MTA deve rimanere aperta: non è un servizio Web Push a browser chiuso.
Le notifiche interne non richiedono permessi; **Notifiche browser** richiede il
permesso solo su clic. La limitazione dei timer delle schede in background o
la perdita di rete può ritardare gli avvisi; il job server continua e lo stato
viene recuperato alla riconnessione. La notifica, da sola, non certifica il
risultato hardware o una misura fatturabile.

## Arranger

Tre schede: **Sorgente**, **Arrangiamento** (incluse le opzioni di conservazione),
**Esecuzione** (timeout 1–240 minuti, predefinito 60, configurazione nativa quando
applicabile). Tutti i campi restano nel DOM durante il cambio scheda e mantengono
i valori. Navigazione delle schede con frecce, Home/End. La zona delle opzioni
ha scorrimento limitato; i contatori CPU, GPU ed elapsed sono in riquadri grandi.
Le fonti e le stime restano esplicite. La finestra può essere chiusa durante il
lavoro; il pulsante **Job AI** rimane disponibile.

Il testo di annullamento distingue richiesta in corso e stato terminale:
`cancelled` con `cancel_requested=true` non mostra più l'attesa di uscita.
La barra si ferma, il pulsante consente una nuova generazione e il messaggio
indica l'annullamento completato. I job completati mantengono il comportamento
di aggiunta della traccia e chiusura automatica dell'Arranger visibile.

## Avanzamento ACE-Step

Il wrapper ACE espone `/mta/tasks/{task_id}/progress`, protetto dalla stessa
API key degli altri controlli. I callback originali del backend sono preservati.
Il worker può leggere le fasi ACE o, con backend non aggiornato, il progresso
annidato nella risposta ufficiale `query_result`. Un endpoint assente o una
telemetria non valida non interrompe la generazione e non duplica l'inferenza.

Per il percorso noto **v0.1.8 Turbo, Euler, senza timesteps personalizzati e
senza troncamento cover-noise**, un hook nel thread della generazione conta le
valutazioni forward DiT completate. Il totale segue `infer_steps` (massimo 20).
Gli altri percorsi mantengono la stima delle fasi o una barra indeterminata.
Se il numero di valutazioni contraddice il totale atteso, il rapporto viene
invalidato. L'hook è temporaneo e il suo cleanup non deve far fallire l'audio.

Il conteggio è osservato sul percorso Python del modello: **non dimostra il
completamento sincronizzato di tutti i kernel GPU**. La percentuale del job
intero è una ponderazione delle fasi, etichettata come **stimata**, non un ETA,
una scansione temporale del brano o una misura di utilizzo GPU. I dati ACE
restano sotto il 100%; il 100% applicativo richiede il completamento MTA e la
pubblicazione della traccia. Lo stesso progetto conserva i propri controlli
preesistenti di finalizzazione, sicurezza, cgroup e accounting.

## Billing GPU

La conferma dell'utente prova che la profilazione funziona sul server, non che
la misura sia completa ed esclusiva per job. Le catture parziali/finali attuali
restano diagnostiche e non fatturabili; `gpu_seconds_estimated` non viene
promosso a `gpu_seconds`. La barra di progresso non è un contatore di consumo.
Questo intervento non abilita il billing, non modifica tariffe o opt-in, non
aggira misure non valide e non indebolisce le verifiche dei ledger.

Prima di una successiva abilitazione servono prove sul reale workload della
copertura di tutte le fasi, dell'attribuzione per task/processo/dispositivo,
delle sovrapposizioni e della concorrenza, oltre a cancellazione, failure e
riavvio. Questa certificazione non è completata nel runner senza ROCm.

## Amministrazione

AI Billing torna a **/settings**; **/admin** è mantenuto come redirect protetto
per i vecchi collegamenti. Corretto anche l'errore del selettore DOM che
interrompeva il caricamento dei dati Billing prima delle richieste iniziali.

Token AI ha navigazione verso Settings, editor, Billing e Job AI; riepiloghi,
selezione di utenti attivi, ricerca e filtro stato, date di creazione e ultimo
uso, rotazione e revoca con conferma. Il token segreto è mostrato una volta,
con copia e nascondi; non viene scritto in localStorage. Le mutazioni includono
l'header CSRF necessario. Tutte le API e la pagina conservano il vincolo admin.

## Prova dell'aggiornamento

1. Aggiornare il server con il nuovo RPM prodotto dal proprio ciclo CI; a coda
   vuota riavviare anche **mta-ace-step.service**, che deve già usare il wrapper
   MTA configurato per il profiler. Il nuovo endpoint di progresso richiede il
   nuovo processo ACE. Non cambiare le configurazioni di sicurezza funzionanti.
2. Ricaricare l'interfaccia. Generare 10 s, osservare CPU/GPU e l'indicazione
   delle fasi/valutazioni, chiudere l'Arranger e aprire Job AI. Alla fine verificare
   notifica, traccia, riproduzione e persistenza dopo riapertura.
3. Provare l'annullamento con Arranger aperto e dal Centro job. Attendere lo
   stato terminale e verificare che non resti il messaggio di attesa del worker.
4. Rimuovere job terminati singolarmente, per intervallo, ultimi N e tutti,
   controllando che il progetto e la contabilità restino invariati. Verificare
   anche un account non amministratore e l'isolamento fra progetti.
5. Aprire Billing → Amministrazione e Token AI → Amministrazione/Editor.
   Provare creazione, copia, rotazione e revoca di un token di prova.
6. Completare la prova lunga: aver superato 600 s è un riscontro favorevole,
   ma occorre anche arrivare a fine job e riaprire la traccia riproducibile.
   Scaricare lo ZIP diagnostico dall'interfaccia dopo le prove.

La generazione breve, l'annullamento, il profiler e il superamento dei 600 s
sono riscontri dell'utente sulla base precedente. Non sono presentati come
collaudo sul server del nuovo pacchetto. Restano da verificare l'esito finale
della prova lunga e l'interfaccia aggiornata sul browser/dispositivo reale.
