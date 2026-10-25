# R210 — Service-regime administration / Amministrazione dei regimi

## Italiano
Il pannello è presente nelle impostazioni amministrative del server e usa le API protette esistenti. Visualizza regime attivo, verifica combinata, eventi outbox in attesa e prenotazioni di transizione. Il pulsante di annullamento richiede conferma e applica il controllo server-side di identità e revisione. Non fornisce un pulsante di cambio regime. Nessuna informazione visualizzata equivale a riconciliazione fiscale, bancaria o attestazione di conformità commerciale. In caso di errore delle API la schermata non dichiara la transizione sicura.

## English
The administration settings panel uses existing administrator-protected APIs for current regime, combined readiness, unresolved payment dispatches and transition reservations. Explicit abort requires confirmation and server-side identity/revision verification. It does not expose regime switching. Displayed data do not constitute financial settlement or authorization for commercial processing. API failures never imply readiness.

## Verification and limits
- Focused tests: 69 passed, 0 failed.
- JS syntax: two files passed `node --check`.
- Full project regression, native GUI interaction, external Stripe/PayPal sandbox and atomic commercial switching: not verified.
- Existing backend fail-closed behavior is retained.
