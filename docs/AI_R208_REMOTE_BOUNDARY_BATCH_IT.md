# MTA Audio Editor 0.3.0-r208 — Remote request boundary batch

## Interventi accorpati (20 verifiche distinte)
1. Rifiuto HTTP non cifrato.
2. Rifiuto di credenziali embedded nell'URL.
3. Rifiuto di query URL.
4. Rifiuto di fragment URL.
5. Validazione porta TCP non numerica.
6. Rifiuto porta 0.
7. Rifiuto percent-encoding nell'authority.
8. Rifiuto percent-encoding nel path.
9. Rifiuto di separator/backslash anomalo.
10. Rifiuto di authority terminata da ':'.
11. Rifiuto di API path non supportati.
12. Tipo del bearer token esplicito e non vuoto.
13. Lunghezza massima bearer token (4096 caratteri).
14. Bearer token privo di whitespace/control e non-ASCII.
15. Timeout positivo, numerico finito, senza booleani, su POST.
16. Timeout positivo, numerico finito, senza booleani, su GET recovery.
17. Le opzioni devono essere un dizionario JSON, senza NaN/Infinity.
18. Il decoder server rifiuta NaN/Infinity e chiavi vuote, non stampabili o con backslash.
19. Request ID fornito di tipo stringa e valido; valori falsy invalidi non generano id nuovi.
20. Validazione bounded delle intestazioni Content-Length e request binding prima della lettura del risultato.

## Verifiche
`PYTHONPATH=. pytest -q tests/test_r208*`: 369 superati, 8 avvisi di deprecazione.
58 nuovi casi di verifica nel modulo `tests/test_r208_remote_transport_boundary_matrix.py`.

## Limiti
Non è una certificazione ROCm/GPU: accounting remoto e attribuzione GPU per singolo job restano da validare/integrate. Nessun addebito GPU sintetizzato.
