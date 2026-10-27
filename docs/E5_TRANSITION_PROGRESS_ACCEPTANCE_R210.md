# E5 — avanzamento, audit e recupero delle transizioni — 27 ottobre 2026

**Criterio originale E5 verificato:** “Complete transition progress, audit and forward recovery controls”. La formulazione e il peso del criterio non cambiano. L'accettazione RC passa da23/42 a **24/42 (57,1%)**. Macroaree interamente chiuse: **0/7**. Release Candidate non raggiunta.

Il cumulativo completo è `MTA-0.3.0-r210-pre-RC-transition-progress-cumulative.zip`. Include tutto il precedente intervento Stripe,ancora successivo alla baseline committata `772fbe7508cc08266466a3746bb51f0fe5d0179b`. Non applicare una catena di patch o ZIP precedenti.

## Cosa mancava e cosa è completo

Il precedente controllo9/9 mostrava soprattutto gli aggiornamenti locali già committati. Il registro non rappresentava in modo completo prenotazioni e annullamenti;non offriva un'unica lettura coerente dei blocchi,delle prove mancanti e delle operazioni ancora aperte. Quel solo risultato non viene usato per promuovere E5.

La nuova vista legge invece il ciclo di vita generale dai registri originali,anche per operazioni storiche non gestite dal controller locale. Usa una transazione di lettura coerente e non esegue richieste ai provider né modifica il regime. L'annullamento precommit usa la prenotazione originale sotto lease esclusivo e registra l'amministratore e l'ora in un audit non modificabile tramite l'applicazione. Il recupero dopo commit conserva il percorso originale di verifica di saldo,periodi,mirror e identità:non esiste un annullamento del commit o un'adozione di ricevute mancanti.

| Stato o condizione | Comportamento operatore verificato |
| --- | --- |
| Nessun passaggio attivo | Regime/revisione reali,storico paginato e nessun progresso inventato |
| Prenotazione prima del commit | Identità e revisione esatte,conteggi registrati,annullamento esplicitamente confermato da mouse o tastiera |
| Prenotazione annullata | Regime,saldi e periodi invariati;amministratore e data dell'azione originale conservati anche sul retry |
| Commit non finalizzato | Barriera visibile;solo recupero in avanti con le prove originali e conferma;annullamento rifiutato anche dall'API |
| Finalizzazione | Stato aggiornato,audit commit/finalizzazione e ripresa coerente;nessuna nuova transizione creata dal polling |
| Operazione storica senza autorità amministrativa originale | Revisione/manutenzione richiesta;nessuna ricevuta o identità ricostruita automaticamente |
| Mirror,saldi,epoca o registri incoerenti | Motivo visibile,azioni pericolose assenti/disabilitate e barriera mantenuta |
| Recupero locale disattivato | Spiegazione specifica sulla configurazione di manutenzione;nessuna attivazione implicita |
| Lettura non disponibile | Informazione precedente invalidata,controlli bloccati,aggiornamento esplicito e recupero della vista |
| Modifica da altra sessione | Polling di sola lettura segue lo stato reale;nessuna azione mutante automatica |

I conteggi sono esplicitamente quelli delle operazioni **registrate**,non una certificazione di tutti gli executor o un preventivo percentuale del drain. Il polling avviene ogni5secondi durante una transizione visibile e si ferma a stato inattivo o documento nascosto. Non invia mai POST. Gli esiti incerti mantengono l'identità originale della richiesta già implementata;il nuovo registro include tutti i passaggi prenotati/annullati/committati/finalizzati.

## Dove si usa

**IT:** Impostazioni → Web App → Regime del servizio → Cambio di regime in manutenzione. “Avanzamento della transizione” mostra stato,regime,revisione,identità e operazioni registrate aperte. “Aggiorna registro” recupera una lettura non disponibile. “Annulla questa prenotazione” compare solo prima del commit verificato. “Completa il recupero” richiede ricevute originali coerenti e la modalità locale supportata. Lo storico senza data o autore non viene presentato come se quei dati fossero stati registrati.

**EN:** Settings → Web App → Service regime → Maintenance regime change. “Transition progress” shows the actual phase,regime,revision,identity and tracked open operations. “Refresh transition audit” retries unavailable reads. “Cancel this reservation” applies only before commit;“Complete recovery” uses original verified evidence and explicit confirmation. Missing historical actor/date evidence remains visibly unavailable.

## Evidenza di accettazione

**32 casi Chromium reali,0 errori e0skip**,con API FastAPI,SQLite,saldi,periodi,journal e ricevute reali. Sono inclusi i9casi originali necessari per il codice UI modificato e23casi di accettazione generale:prenotazione/annullamento,prove mancanti e legacy,epoca incoerente,recupero disattivato,errori di lettura,polling,e pagina completa delle impostazioni. IT/EN,390/1280pixel,tastiera e8scansioni axe-core del componente nella pagina completa,senza esclusioni di regole e senza violazioni rilevate. Non è una certificazione di tecnologie assistive o runtime nativi su tutti i sistemi.

Lo script `scripts/run_transition_progress_chromium.py` richiede l'identità esatta di tutti32casi e nessuno skip/failure/error. Richiede Playwright1.51.0,Chromium build1161 e il file test-only axe-core4.10.3 indicato da `MTA_TEST_AXE_CORE`,con SHA256 esatto `880970c081707360e64f34cea25ff91892f5bc95675b0776925b9709dd8a68bb`. Il controllo cancella una vecchia attestazione prima di iniziare:prerequisiti mancanti o dati incompleti non possono riutilizzare un precedente successo.

Esito,XML,log e impronte originali del run: `validation/r210/transition-progress-chromium/`. Aggregato con test API/regressione/gate e provenienza delle correzioni: `validation/r210/transition-progress-result.json`. I fallimenti iniziali sono conservati. Corretto un difetto reale nel registro vuoto (`ul` con testo diretto invece di `li`);il bridge del browser usa gli effettivi HTTP500 del server anche durante manutenzione,senza farli diventare eccezioni del test. Le preferenze di lingua delle fixture sono impostate prima della barriera;il vincolo di scrittura durante recupero resta attivo.

Nessuna suite Stripe invariata o CI completa ripetuta. La CI standard40480180716 resta prova della baseline772fbe7;le modifiche correnti non sono dichiarate già validate dalla CI GitHub. Chromium è stato eseguito qui,quindi non serve richiedere un nuovo run esterno solo per soddisfare questo prerequisito.

## Separazione dei criteri e limiti invariati

E5 riguarda i controlli di avanzamento,audit e recupero;ora comprende anche le fasi e i rifiuti generali precedentemente non coperti. Non viene promosso E4,che richiede il completamento del workflow sensibile di cambio generale. C2,C3,C5,C6 e D6 restano aperti:questa verifica non certifica drain distribuito,obbligazioni globali/provider/legacy o il cambio generale. Restano anche le verifiche di diritti,executor e target esterni già documentate. Le attivazioni globali rimangono false e il cambio locale default-off;nessuna soglia o condizione di accettazione backend viene allentata.

Nuovo schema solo di audit: `regime_reservation_aborts`,con transizione/revisione,attore e timestamp. È esplicitamente inventariato come metadato;non contiene saldi o istruzioni di pagamento. L'annullamento già storico senza quell'audit non viene retrocertificato. Le prove finanziarie continuano a essere verificate dal controller originale prima del recupero e del rilascio della barriera.

Nessun commit,staging,push,dispatch CI o intervento su GitHub/server/provider reali eseguito. L'utente gestisce il commit.
Commit cumulativo suggerito dopo772fbe7:
`Harden Stripe reconciliation and complete transition progress, audit and recovery`
