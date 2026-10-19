> Stato aggiornato / Updated state: [SUBSCRIPTION_ONLY_CREDITS_DEVICE_R210.md](SUBSCRIPTION_ONLY_CREDITS_DEVICE_R210.md). Le descrizioni precedenti sono storiche.

# r210 — accesso con abbonamento o crediti / subscription or credit access

## Italiano

In Amministrazione → Abbonamenti e crediti, cercare un utente digitando parte di nome visualizzato, username o email. I risultati arrivano dal server durante la digitazione (massimo 20 per ricerca). Il selettore permette di scegliere esplicitamente l'utente. Il permesso «Richiedi un abbonamento o crediti» abilita anche l'addebito a consumo senza abbonamento; l'admin non può applicarlo agli amministratori. I controlli sono disattivati per default e non cambiano implicitamente i vecchi account.

L'accesso richiede un piano attivo e finanziato, anche a canone zero, oppure un saldo positivo con billing a crediti. All'apertura dell'editor un utente senza copertura viene indirizzato al profilo. Un editor già aperto mostra entro circa 15 secondi (prima se torna in primo piano) un avviso con link al profilo; non viene ricaricato e i job e i risultati in corso non vengono persi. Creazione di nuovi progetti/import e ammissione AI sono controllate anche dal backend; lettura, salvataggi dei risultati, stato e cancellazione dei job rimangono disponibili. Le native locali non sono soggette al gate web; i job remoti autenticati con token rispettano l'ammissione del server.

Il profilo presenta le opzioni disponibili per abbonarsi e l'indicazione di richiedere/acquistare crediti tramite l'amministratore. **Non è integrato un gateway di pagamento**: le assegnazioni dell'admin sono il meccanismo di ricarica disponibile. Per l'attivazione autonoma dei piani vanno abilitate le opzioni globali Abbonamenti e Attivazione autonoma. L'admin può preparare una prova di 7 giorni o una promozione settimanale gratuita con i pulsanti dedicati, controllare i campi e assegnare il contratto. Il motivo promo esenta dal canone, non dalle quote. La prova resta utilizzabile una sola volta per account e conserva le regole di rinnovo già implementate.

Il valore nominale predefinito di un credito è **0,10 EUR**, modificabile. Il registro conserva importi in micro-EUR: cambiare il valore nominale modifica la rappresentazione e la conversione delle nuove ricariche, senza rivalutare gli importi già assegnati. La ricarica in numero di crediti include una quotazione del valore nominale; il server rifiuta quotazioni obsolete. Motivazione e ID idempotente rendono verificabili le assegnazioni.

Ogni job ammesso congela le tariffe e un tetto di spesa. I worker dello stesso job della coda condividono un unico tetto, senza duplicare il saldo disponibile. L'esaurimento dei crediti **non cancella il job già ammesso**. Alla chiusura l'addebito CPU/GPU è il minimo fra costo effettivo, tetto residuo e saldo disponibile: non crea nuovo debito CPU/GPU. Le ricariche successive non aumentano il tetto dei job già ammessi. Partire senza crediti non autorizza extra gratuiti: al superamento della quota inclusa resta prevista la cancellazione se non erano disponibili crediti al momento dell’ammissione. I consumi effettivi rimangono integralmente nell'accounting; i movimenti mostrano gli importi non addebitati. Misure non valide non diventano fatturabili. I limiti manuali e le quote senza autorizzazione extra restano effettivi: questa regola non elimina limiti di sicurezza, timeout o cancellazioni richieste dall'utente.

Con un piano a prezzo zero le risorse incluse hanno costo zero ma i limiti restano applicati. Gli extra CPU/GPU autorizzati usano crediti alle tariffe ordinarie. Le assegnazioni di piano dall'interfaccia admin consentono tali extra; l'utente può comunque disattivarli dal profilo. Le quote disco e l'integrazione temporale dello storage mantengono la semantica precedente: la capienza extra assegnata è addebitata per il tempo effettivo di assegnazione, anche quando vuota, e può maturare un saldo negativo se non ridotta o resa gratuita dall'admin. Il tetto di spesa del job si applica al calcolo CPU/GPU, non sostituisce il contratto storage.

### Tariffe iniziali e stima storage

| Categoria | Default |
| --- | --- |
| CPU | 0,000001 EUR/s |
| GPU | 0,000010 EUR/s |
| Storage | **0,000020 EUR/GiB·ora** |
| Credito nominale | 0,10 EUR |

Stima richiesta dal gestore: un supporto da 4 TB decimali (circa 3725,29 GiB) a 800 EUR, ammortizzato su 3 anni × 365 giorni × 24 ore, comporta un costo hardware di circa 0,00000817 EUR/GiB·ora. Il default scelto è circa 2,45 volte tale costo, come margine indicativo per ridondanza, energia e gestione. Non è una misura dei costi reali dell'istanza. Equivale a 0,0144 EUR/GiB per 30 giorni, circa 53,64 EUR per 4 TB assegnati per 30 giorni. L'admin può sostituirlo. Le tariffe mancanti vengono inizializzate prospetticamente quando si abilita il sistema/il billing a crediti; tariffe già configurate, incluse quelle a zero, e periodi chiusi non vengono sovrascritti. Il modulo espone i default anche prima dell'attivazione; il pulsante Salva tariffe registra le tre categorie insieme, senza aggiornamenti parziali.

Il cumulativo conserva la scelta del motore audio e le correzioni macOS del checkpoint precedente. Vedere `CPP_AUDIO_ENGINE_CHECKPOINT_R210.md` per la continuazione della timeline C++. Versione **0.3.0-r210**, senza commit/push/tag/release.

## English

Administration → Subscriptions and credits provides a dynamic server-side partial display-name/username/email search, explicit user selection, one switch requiring a funded subscription or credits, trial/promotion shortcuts, free credit grants, and category tariff editing. Administrators are exempt from mandatory paid access. Existing accounts are unchanged unless explicitly configured.

Blocked users opening the editor are sent to their profile. Existing editor sessions receive a notice within about 15 seconds without reloading or discarding pending work. Backend checks protect new project/import and AI admission, while job polling, cancellation and result saving remain available. Local native sessions are exempt; remote AI token jobs use server admission. Self-service plans require global enablement. Credit purchases are arranged with the operator and fulfilled by administrator grants; **no payment processor is integrated**.

A nominal credit defaults to EUR0.10. Money remains stored as integer micro-EUR; changing credit value does not revalue existing monetary balances. Quoted conversions reject stale values. Zero-price/promotion plans keep their resource limits. Authorized compute overages use ordinary tariffs. Each admitted queue job shares a frozen spending ceiling and tariff quote across its worker steps. Running jobs continue when credits run out; final CPU/GPU charges cannot exceed that ceiling or the remaining wallet. Later grants do not increase the original ceiling. Starting with no credits does not authorize free overages: included quota exhaustion still stops a job that had no funded overage authorization at admission. Full consumption and waived charges remain visible in accounting. Manual quotas, non-authorized overages, metering validation, safety limits and user cancellation remain enforced.

Default CPU/GPU tariffs are EUR0.000001/s and EUR0.000010/s. Storage defaults to **EUR0.000020/GiB-hour**: assuming EUR800 for 4 decimal TB over three years, the hardware component is about EUR0.00000817/GiB-hour, with a roughly 2.45× allowance for redundancy, energy and management. This is an estimate, not measured operating cost. It equals EUR0.0144/GiB over 30 days. Existing configured rates, including zero, are preserved; missing defaults start prospectively. All three tariff edits commit atomically. Storage retains prior time-based assigned-capacity pricing and may accrue a negative balance until extra capacity is reduced or sponsored; the new job spending cap concerns CPU/GPU only.

Native C++ prepared timeline scheduling now participates in offline mixing; current transport and live VST3 limitations remain documented in the C++ checkpoint. Full test evidence is under `validation/r210-credit-timeline-*`; real native hardware and production-server acceptance remain necessary.

## Verifica del cumulativo / cumulative verification

- Suite finale: **4038 passed, 5 skipped, 10 deselected**, copertura / coverage **77,62%**, 235,51 s.
- Test mirati / targeted: **95 passed**. CMake/C++ reale, render end-to-end, query di timeline, API, migrazione, crediti e tariffe.
- Ruff su app/native/tests/build helper, sintassi JavaScript e parsing YAML workflow: passati / passed.
- 10 casi AF_UNIX esclusi dopo `PermissionError(1)` alla creazione del socket. 4 test richiedono Steinberg SDK/ADelay opzionali e uno API Win32 reali.
- Nessuna prova funzionale su server di produzione ROCm, hardware audio Windows/macOS o VST3 commerciali / no production ROCm server, real native audio hardware or commercial VST3 acceptance performed.
- Archive checks: all previous files retained, CRC and every archive entry compared with source bytes; SHA-256 delivered separately. No commit, push, tag or release.
