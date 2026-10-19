> Aggiornamento / Update: [LIVE_VST3_HOST_R210.md](LIVE_VST3_HOST_R210.md). Le limitazioni live descritte nei checkpoint precedenti sono storiche.

# r210 — Crediti per abbonamenti e trasporto nativo / Subscription credits and device transport

## Italiano

Questa nota aggiorna i precedenti checkpoint; la revisione resta **0.3.0-r210**.

### Crediti e abbonamenti

I crediti coprono solo gli extra quota autorizzati di un abbonamento attivo, compresi trial e promo. Non sostituiscono l'abbonamento. Senza possibilità di abbonarsi l'utente conserva l'accounting ma non può essere fatturato né usare crediti. Disabilitare questa possibilità chiude il periodo attivo; lo storico e i saldi restano conservati. Gli amministratori restano esenti per default.

L'amministratore deve abilitare il servizio globale «Abilita crediti». Il valore predefinito è disattivato. I tagli iniziali sono 5, 10, 20 e 50 EUR, configurabili; il valore nominale iniziale è 0,10 EUR per credito. Un amministratore può caricare crediti soltanto a utenti eleggibili. Le tariffe già configurate non vengono sovrascritte.

La pagina personale `/account/credits` presenta i tagli acquistabili e il saldo. Occorrono servizio abilitato, autorizzazione ad abbonarsi e abbonamento/promo attivo. I canoni del piano sono registrati separatamente come importi dovuti all'operatore e non consumano crediti: l'incasso ricorrente automatico degli abbonamenti non è implementato da questo intervento.

Quando le quote CPU/GPU sono esaurite e non ci sono crediti, il job viene rifiutato prima di creare una voce di coda; il popup propone rinnovo, ricarica se consentita e contatto amministratore. Un job già ammesso conserva un tetto condiviso fra i suoi worker: può completarsi dopo l'esaurimento del saldo senza ulteriori addebiti CPU/GPU, mantenendo tutti i consumi registrati. Lo storage conserva il proprio conteggio temporale per l'allocazione extra autorizzata.

### Configurazione acquisti Stripe

1. Configurare la URL pubblica HTTPS nei dati legali dell'istanza.
2. Nel proprio account Stripe creare le chiavi per l'ambiente test; configurare in amministrazione la chiave segreta e il segreto webhook. Le chiavi non sono restituite dall'API e sono cifrate con il segreto dell'istanza: includerlo nei backup protetti.
3. Registrare l'endpoint pubblico `https://mta.apps.desalvo.eu/api/billing/credits/stripe-webhook` (adattare al proprio dominio). Abilitare `checkout.session.completed`, `checkout.session.async_payment_succeeded` e `charge.refunded`.
4. Provare acquisto, evento duplicato, importo errato, pagamento non completato e rimborso in ambiente test prima di usare chiavi live.
5. Il redirect di successo non accredita nulla: il server verifica firma, timestamp, ordine, sessione, valuta, importo e stato pagato del webhook. I rimborsi cumulativi sono idempotenti e possono produrre un saldo negativo se il credito è già stato speso. Le contestazioni/chargeback richiedono riconciliazione amministrativa; non è presente una procedura automatica dedicata.

Nessun pagamento reale viene effettuato dai test della suite.

### Dati legali

Sono obbligatori soltanto titolare, Paese di stabilimento, email assistenza/reclami, URL pubblica HTTPS e data di efficacia. I campi opzionali vuoti non sono menzionati nei PDF. Lo stato di revisione rimane informativo; compilare questi cinque campi permette il salvataggio e la generazione. Questo controllo verifica la completezza dei dati richiesti dall'applicazione, non certifica l'adeguatezza legale di ogni specifica istanza.

### Motore C++ e VST3: stato effettivo

Il motore corrente rimane predefinito e selezionabile. Con il motore C++ nelle app native il mix preparato viene riprodotto sul dispositivo di uscita predefinito tramite miniaudio 0.11.23. Play, pausa, seek, fine file e clock sono nativi; decodifica e I/O avvengono nel produttore, fuori dalla callback audio. La callback usa un ring buffer fisso e atomiche, senza Python, plugin o allocazioni. Un backend nullo è consentito soltanto nei test espliciti, mai come uscita di produzione. Arresti inattesi del dispositivo risultano come errore. Il cambio motore e la chiusura dell'app arrestano il dispositivo.

Gli effetti vengono preparati prima della riproduzione; modificarli ricostruisce il mix con un'interruzione. Sono corretti ordine misto insert interni/VST3, master VST3, stato binario e parametri, editor originale in processo separato e invocazione worker nelle app congelate Windows/macOS. L'editor applica lo stato alla chiusura. Pedalboard resta il processore VST3 offline.

**Non è completato l'hosting VST3 real time nella callback C++, né il monitoring live/MIDI.** Non sono inclusi selettore del dispositivo, registrazione o trasporto ASIO dedicato. `native_host_ready` resta falso; l'apertura di un dispositivo reale non equivale a certificazione. Servono prove di ascolto su Windows/macOS e plugin reali. I test null verificano la callback compilata e il clock, non l'hardware.

## English

This note supersedes earlier checkpoint descriptions. The version remains **0.3.0-r210**.

Credits cover authorized overages of an active subscription, trial or promotion only. They cannot replace a subscription. Users who cannot subscribe retain usage accounting but have no billing or credit usage. Disabling subscription eligibility closes the active period while retaining history and wallet balances. Administrators remain exempt by default.

The global credit service defaults to off. Administrators can configure the initial EUR 5/10/20/50 purchase denominations and grant credits to eligible users. The initial nominal value is EUR 0.10 per credit; existing tariffs are preserved. `/account/credits` requires global service, user eligibility and an active plan. Base plan fees are separate operator receivables, never credit debits. Automatic recurring subscription collection is not implemented here.

Exhausted compute allowances with zero credits cause rejection before queue insertion. Already admitted jobs and their worker steps share a spending ceiling and finish without further CPU/GPU charges after the balance is exhausted; full consumption remains recorded. Authorized storage allocation retains its separate time-based accounting.

For Stripe, configure the public HTTPS URL, secret API key and webhook secret in administration, and register `/api/billing/credits/stripe-webhook` with `checkout.session.completed`, `checkout.session.async_payment_succeeded` and `charge.refunded`. Test before enabling live keys. Only verified signed paid events credit the wallet; success redirects do not. Order, session, amount, currency, event identity and timestamp are checked. Cumulative refunds are idempotent and can leave a negative balance when credits have been spent. Disputes require operator reconciliation. Tests use a mocked provider and make no real payments. Protect the instance secret in backups because it encrypts payment credentials.

The five mandatory legal fields are controller, country of establishment, support/complaints email, public HTTPS URL and effective date. Empty optional fields are omitted from generated PDFs. Review status is informational. Application completeness checks do not certify legal suitability for every deployment.

The current audio engine remains the default option. Selecting C++ enables native default-device playback of a prepared mix using pinned miniaudio 0.11.23. Native play/pause/seek/EOF and clock use a fixed ring buffer, with decoding off the audio callback. Production refuses a null output backend. Switching engines or closing the application stops the device; unexpected stops are reported as failures.

VST3 fixes include mixed insert ordering, master inserts, binary state and parameter restoration, original plugin GUI in a separate process and frozen Windows/macOS worker dispatch. GUI state is applied when the editor closes. Effects remain prepared offline through Pedalboard; editing them rebuilds the mix and interrupts playback. **Real-time C++ VST3 callback hosting and live/MIDI monitoring are unfinished.** Device selection, recording and a dedicated ASIO transport are not included. `native_host_ready` remains false. Compiled null-device tests are not physical hardware acceptance; Windows/macOS listening and real plugin tests remain necessary.

## Upstream references

- miniaudio: https://miniaud.io/docs/manual/index.html
- Pedalboard: https://spotify.github.io/pedalboard/reference/pedalboard.html
- Stripe Checkout: https://docs.stripe.com/api/checkout/sessions/create
- Stripe webhooks: https://docs.stripe.com/webhooks
