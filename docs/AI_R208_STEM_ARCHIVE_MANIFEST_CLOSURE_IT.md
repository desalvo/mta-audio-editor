# r208 — Chiusura validazione manifest per gli stem remoti

La funzione di importazione stem con journal e quella da discovery condividono la medesima validazione dell'archivio. Prima di iniziare la transazione di pubblicazione vengono controllati: numero e nomi delle voci ZIP, duplicati, traversal, symlink, cifratura, manifest v1, corrispondenza biunivoca tra manifest e archivio, tipo MIME, estensione, dimensione totale decompresso, integrità opzionale SHA-256 di **tutti** i file (anche metadata JSON/testo), sintassi JSON e struttura WAV. Gli errori di validazione sono fail-closed (HTTP 422) e non avviano la transazione.

Test locali: 29 passed, 8 warnings (suite stem r208 + importazione strutturata). Non costituiscono certificazione di tutta l'applicazione, della pubblicazione con guasti reali o del calcolo GPU.
