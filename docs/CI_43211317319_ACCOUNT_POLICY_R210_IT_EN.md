# CI43211317319: revoca abbonamenti / Subscription permission revocation

## Italiano

Run [43211317319](https://github.com/desalvo/mta-audio-editor/actions/runs/43211317319)
sul commit55b98f8: **failure**, un solo test browser fallito,9083 passati,
126 saltati,copertura78,31%. Sicurezza e VST3 sono passati; container,
installer e pubblicazioni sono stati saltati dopo il fallimento Quality.

Il caso account mobile390px/inglese/permission_disabled pretendeva il
pulsante data-cancel, come negli scenari con abbonamento attivo.
La configurazione dello scenario revoca subscriptions_allowed; set_policy
chiude l'abbonamento e rimuove il rinnovo. L'esistenza di un controllo del
contratto non è quindi l'invariante da verificare per questa revoca.

Correzione nel solo test: lo scenario di revoca verifica l'assenza di nuove
attivazioni, salvataggio del prossimo rinnovo e link di acquisto crediti.
L'assert sul pulsante di annullamento resta per active,trial,paid e
credits_disabled. Tutte le32 combinazioni scenario/lingua/larghezza restano
presenti; nessun timeout esteso e nessun caso saltato. Le quattro prove
end-to-end di annullamento effettivo del rinnovo restano incluse.

Validazione locale: **67 test API di abbonamenti,trial,storage,contratti e
accesso ai crediti passati**, più **5 prove API→DOM** con risposte reali e
subscriptions.js di produzione (happy-dom) per active,trial,credits_disabled,
permission_disabled e no_plan. Verificati anche i pulsanti di annullamento
degli stati attivi. Ruff completo e sintassi JavaScript passano.
Le prove DOM non sono prove Chromium: il browser locale non può avviarsi per
le restrizioni del kernel sui socket. La verifica browser/responsive/tastiera
rimane alla nuova fullCI sullo SHA corretto.

Nessun modulo applicativo, JavaScript, logica contabile, tariffa o permesso
del prodotto modificato. Versione0.3.0-r210 e PRE-RC73% invariati.
I risultati verdi di858dea2 non attestano55b98f8 né il successivo fix.

## English

The full run failed one account browser assertion (mobile390px,English,
subscription permission revoked);9083 tests passed and126 skipped,78.31%
coverage. Security and VST3 passed; downstream packaging/publication skipped.

The test incorrectly required an active-subscription cancellation control
after revoking subscription permission. Check that activation,renewal-save
and credit-purchase actions are unavailable instead. Retain cancellation
assertions for active/trial/paid/credits-disabled plans and all32 account
scenario/language/viewport combinations, plus actual renewal cancellation
flows. No skips,timeouts or production accounting/access code changed.

Local verification:67 API regressions and5 actual-API→production-JS DOM cases
pass, with full scoped Ruff and JavaScript syntax checks. Local Chromium
cannot start under the kernel socket restrictions; DOM tests do not certify
browser rendering,keyboard or responsive behaviour. The corrected main full
CI must complete before declaring new builds or packages published.

