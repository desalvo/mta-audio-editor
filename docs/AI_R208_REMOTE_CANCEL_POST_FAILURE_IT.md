# MTA Audio Editor 0.3.0-r208 – cancellazione dopo invio remoto

Il client propagha ora una richiesta di cancellazione durevole e autenticata al server remoto quando rileva una cancellazione dopo avere spedito la POST o durante la ricezione della risposta. La chiamata è best effort: un errore di rete non viene interpretato come una prova di arresto fisico del worker. La cancellazione locale impedisce anche il recupero e l'accettazione del risultato tardivo.

## Verifiche

793 test della suite `tests/test_r208*` superati, inclusi tre nuovi test: cancellazione dopo errore di rete, dopo arrivo del risultato e con endpoint di cancellazione irraggiungibile. Non sono stati eseguiti test fisici EL10/ROCm.

## Limiti residui

Le chiamate HTTPS sincrone già bloccate non sono interrompibili immediatamente; l'arresto effettivo dell'inferenza sul worker e la misurazione GPU attendibile richiedono ulteriore lavoro e test hardware. La correzione rappresenta una singola integrazione funzionale con più scenari, non oltre 100 funzionalità indipendenti.
