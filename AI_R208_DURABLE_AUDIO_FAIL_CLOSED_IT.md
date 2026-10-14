# MTA Audio Editor 0.3.0-r208 — admission audio durevole fail-closed

## Modifica
- Qualunque job Arranger/Remix con un payload persistito è soggetto al controllo della finalizzazione audio, anche quando il JSON è illeggibile o lo schema è incompatibile.
- La fase di claim blocca i job con payload malformati, in modo che non eseguano inferenza senza un'identità durevole verificabile.
- I job puramente legacy senza payload continuano a seguire il precedente percorso in memoria.
- Test di regressione: quattro payload non validi e un caso legacy senza payload.

## Verifiche e limiti
- `PYTHONPATH=. pytest -q tests/test_r208*`: 293 superati.
- Certificazione dei worker remoti, attribuzione GPU per job e crash test sul sistema EL10/ROCm ancora da completare; non dichiarare la certificazione hardware.
