# MTA Audio Editor 0.3.0-r208 — Tre chiusure upload

1. Upload ordinario: se la registrazione della traccia o `save_project` fallisce, il nuovo file audio non referenziato viene eliminato. File audio già presenti non vengono coinvolti.
2. Sostituzione traccia: se registrazione o salvataggio falliscono, il nuovo file viene eliminato, mentre quello originale rimane disponibile.
3. Validazione anticipata: valori `sync_mode` non previsti vengono respinti prima di acquisire il progetto e prima di salvare un nuovo upload, in entrambi gli endpoint.

**Limiti:** non è ancora un commit atomico filesystem/JSON in caso di SIGKILL o crash durante `save_project`; per la persistenza forte serve un journal di transazione. I test sono locali, non hardware.
