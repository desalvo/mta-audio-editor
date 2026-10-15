# MTA 0.3.0-r208 — riconciliazione delle richieste remote dopo crash

## Interventi
- Il recupero owner-only dello stato remoto e del risultato riconcilia una richiesta `admitted` se una cache durevole completa e verificata era stata pubblicata prima dell'interruzione.
- La lettura dei byte e dei metadati avviene sotto lock per chiave, con controlli su inode, hardlink, scadenza, tipo MIME e SHA-256.
- La transizione del database è idempotente e non avvia inferenza, non duplica job e non fabbrica evidenze GPU.
- Un cache miss, una corruzione o una scadenza mantengono la richiesta in stato `admitted` e richiedono indagine manuale.

## Verifiche
- `PYTHONPATH=. pytest -q tests/test_r208*`: 285 test superati nell'ambiente locale.
- Non eseguita certificazione GPU/ROCm su ollama-02.

## Limiti residui
- Questo intervento non crea automaticamente misurazioni GPU e non certifica la contabilizzazione end-to-end di tutti i worker remoti.
- Le richieste senza cache configurata non possono usufruire di questo recupero.
