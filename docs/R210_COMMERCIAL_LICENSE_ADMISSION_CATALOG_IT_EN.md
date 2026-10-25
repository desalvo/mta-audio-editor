# r210 — Licenze AI, coerenza ammissione/catalogo

Il catalogo amministrativo espone `available_in_current_regime`, `effective_mode`, `license_denial_reason` oltre al `mode` configurato. Questi campi devono controllare la disabilitazione delle opzioni UI; `mode` non rappresenta una autorizzazione. Un modello disabilitato resta visibile a fini diagnostici. `evaluate_model` blocca policy importate con autorizzazione `noncommercial_context` sotto COMMERCIAL e gli override `cost_recovery` di Qixuan. Non sono stati cambiati gli obblighi di licenza.

## Verification / Verifica

156 focused regime/license tests passed, one fork deprecation warning. No real providers, distributed deployment, full CI or complete AI-adapter route audit; commercial switching disabled.

## English

Administrative license catalogs now provide effective availability and denial reasons; configured mode alone is not admission. Imported noncommercial-context authorizations are denied under COMMERCIAL, and Qixuan cannot be overridden into paid inference. Model execution must still invoke `evaluate_model` at the server boundary; remaining adapters and interfaces require whole-system tests.
