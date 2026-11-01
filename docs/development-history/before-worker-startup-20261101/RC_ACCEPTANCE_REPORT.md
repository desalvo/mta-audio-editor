# Accettazione RC MTA 0.3.0-r210 — 1 novembre 2026

**RC: 81,0% = 34/42**, perimetro `precommercial-20261030`; **PRE-RC**, 8 criteri aperti e D/E complete (2/7). A4 promosso a verified, A5 resta verified. Nessun testo, peso o denominatore cambiato.

Matrice A4, comportamento e limiti in `PAYPAL_CASH_HISTORY_ACCEPTANCE_R210.md`. **927 casi distinti passati, 48 nuovi; zero fallimenti/errori, 20 skip browser espliciti**. I 48 nuovi casi passano, incluso SIGKILL. API provider simulate; nessun nuovo collaudo browser/provider. Ruff, compilazione e quattro gate passano; nessuna nuova CI remota.

Cumulativo `MTA-0.3.0-r210-pre-RC-paypal-cash-history-cumulative.zip`; evidenza `validation/r210/paypal-cash-history/result.json`. Baseline confermata `ee4e37fd30c39a72638b303b01ca0cd5b090f272`, commit differito.

Restano **A6,B6,C6,F4,F5,F6,G5,G6**. Prerequisiti A6 nel rapporto dedicato; C6 conserva lavoro di integrazione e F4/F6 contratti e revisioni indipendenti. Il vecchio perimetro v1 resta storico e non direttamente comparabile.
