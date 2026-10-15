# Outbox e recovery audio — MTA 0.3.0-r208

## Implementazione

- `app/ai_publish_outbox.py`: staging WAV persistente, SHA-256, manifest SQLite in `/var/lib/mta/ai-jobs/publication` (personalizzabile tramite `MTA_AI_JOB_STATE_DIR`), lock `flock` interprocesso, consumatore idempotente e replay delle pubblicazioni pending.
- Arranger/Remix asincroni: l'inferenza salva prima il WAV nella Outbox; la pubblicazione usa lo stesso identificativo del job. Al riavvio le pubblicazioni incomplete vengono riprese prima dei nuovi job queued.
- Lo stato `interrupted` viene riconciliato con `completed` **solo dopo** la conferma della pubblicazione nella Outbox; i job cancellati non sono convertiti in completed.
- Il risultato WAV presente è verificato tramite checksum e riutilizzato in caso di crash prima del salvataggio del progetto; un risultato differente è bloccato.

## Crash injection offline (nessuna modifica ai servizi)

Eseguire dalla radice dei sorgenti estratti:

```bash
python scripts/crash_inject_ai_outbox_r208.py
python -m pytest -q tests/test_r208_audio_publication_outbox.py tests/test_r208_outbox_queue_reconciliation.py
python scripts/certify_ai_r208.py --hardware --output ai-hardware-probe.json
```

Lo script di crash injection usa una TemporaryDirectory e un subprocess che esce con `os._exit(77)` **dopo** un side-effect simulato e **prima** del receipt SQLite. Il subprocess successivo verifica il replay senza duplicare il side-effect (consumer idempotente). Non usare lo script per terminare il servizio di produzione.

## Collaudo su ollama-02 (Rocky EL10 + ROCm)

1. Fare backup del DB, dei progetti e di `/var/lib/mta/ai-jobs`, installare il pacchetto solo in ambiente di test o finestra di manutenzione.
2. Verificare `rocminfo | grep -i gfx1151`, `amd-smi list`, `python -c 'import torch; print(torch.version.hip, torch.cuda.is_available())'` nell'ambiente Python usato dal **servizio**.
3. Avviare `scripts/certify_ai_r208.py --hardware` e conservare il JSON con `journalctl -u mta-server -u mta-ace-step --since '15 minutes ago'` (sanitizzare prima della condivisione).
4. Per **ognuno**: ACE-Step, Whisper, Demucs, DrumSep, SAM Audio, separazione vocale, analisi accordi, inviare un breve WAV di test, verificare output valido, SHA-256, progresso reale, backend effettivo CPU/HIP, annullamento e invio ripetuto con stessa Idempotency-Key. Annotare esito e log; un test `torch.cuda.is_available()` non certifica l'adapter.
5. Usare uno staging isolato per il crash test reale: stoppare un worker *di prova* dopo la scrittura della Outbox, riavviare il server, confermare un solo clip pubblicato, una sola ricevuta terminale e nessuna ripetizione dell'inferenza. **Non uccidere un processo condiviso di produzione**.

## Limiti e condizioni di certificazione

**Non è ancora certificata l'atomicità end-to-end comprensiva del billing.** I job Arranger/Remix non sono associati automaticamente a una voce corrispondente nel ledger `ai_compute_jobs`; il ledger è un database distinto e non esiste ancora una delivery billing dell'Outbox collegata a tutti gli ingressi AI. Servono una chiave di correlazione comune, un evento Outbox `billing_pending`, delivery persistente con `finish_job_idempotent`, conferma contabile e gating dello stato `completed` fino alla conferma. Anche la concorrenza di pubblicazioni diverse sullo stesso progetto e la durabilità del salvataggio del progetto su storage remoto richiedono test di integrazione. Nessuna certificazione degli adapter EL10/ROCm è dichiarata senza inferenza reale.
