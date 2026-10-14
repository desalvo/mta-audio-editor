# MTA Audio Editor 0.3.0-r208 — verifica completa della lettura dei piani

Questo checkpoint conserva tutti i contenuti del cumulativo `MTA-r208-planning-global-audit-cumulative.zip` e rafforza il journal SQLite di sola pianificazione.

## Intervento
- `get` verifica l'integrità dei record visibili a progetto e proprietario prima di restituire un elemento.
- `list` esegue lo stesso audit prima di applicare paginazione e filtro stato: un record alterato fuori pagina non viene ignorato.
- L'audit è confinato all'ambito del proprietario per non esporre record di altri utenti.
- Nessuna inferenza viene eseguita dal journal e nessun evento è fatturabile.

## Test
31 passed: test di pianificazione, storico, API, regressione della coda e nuove prove di record corrotti fuori pagina, stato indicizzato alterato e isolamento degli utenti.

## Limiti
La verifica integrale può essere costosa per ogni lettura, fino a 128 record, e non fornisce ACID globale tra sistemi. Rimangono aperti lifecycle inferenza reale, native/server, billing, metering GPU, installer e certificazione multipiattaforma.
