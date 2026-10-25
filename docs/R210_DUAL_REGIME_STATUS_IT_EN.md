# MTA 0.3.0-r210 — Service regimes / Regimi del servizio

## IT — Stato effettivo
Il nucleo `app/service_regime.py` è un componente preparatorio: mantiene `NON_COMMERCIAL` come default sicuro, preserva la configurazione preesistente e produce un piano di transizione senza mutare il ledger. Non abilita la vendita di crediti, abbonamenti, billing alternativo o cambio regime lato server. L'attivazione richiede migrazioni, blocchi server-side e una riconciliazione contabile verificata. Non esporre il selettore nell'UI finché le verifiche end-to-end non siano completate. I regolamenti IT/EN allegati nelle specifiche sono bozze da validare giuridicamente, non condizioni già pubblicate.

## EN — Actual status
`app/service_regime.py` is preparatory infrastructure only: safe `NON_COMMERCIAL` default, conservative existing-configuration handling, and a read-only transition plan. It does not activate subscriptions, prepaid credits, alternate billing or live server regime switching. Schema migrations, server-side admission, financial reconciliation and end-to-end acceptance are required before enabling the administrator selector. Supplied legal text is draft material and has not been published as service terms.
