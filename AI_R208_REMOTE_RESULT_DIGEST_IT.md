# MTA 0.3.0-r208 — Integrità delle consegne remote

- Il server allega `X-MTA-AI-Result-SHA256` ai risultati sia POST sia GET di recupero idempotente.
- Il client confronta il digest con i byte ricevuti e rifiuta checksum assenti di validità, alterati o discordanti (il campo è facoltativo per compatibilità con server precedenti).
- Non effettua alcuna inferenza locale come fallback e non accredita tempo GPU dedotto dalle dimensioni del risultato.
- Test locali: `PYTHONPATH=. pytest -q tests/test_r208*` = 270 superati; anche compileall Python e bash -n dell'installer.
- Limiti: non è una prova crittografica indipendente dall'autenticazione TLS, non certifica metering GPU o tutte le integrazioni di billing remoto. Restano necessari crash injection e test EL10/ROCm su ollama-02.
