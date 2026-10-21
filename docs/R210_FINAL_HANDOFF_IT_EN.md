# r210 — Passaggio ai collaudi / Test handoff

## IT
La versione resta 0.3.0-r210. Verifiche offline: 143 test superati, 0 falliti, 15 saltati. Non certifica la chiusura integrale delle tre macroaree.

**Operazioni prima della certificazione:**
1. Inventariare e verificare le licenze indipendenti del codice, dei checkpoint, dei vocoder, delle voicebank, dei modelli ausiliari e dei SoundFont in base al regime non commerciale/commerciale; non abilitare gli asset incompatibili.
2. Sul server di prova installare runtime e asset autorizzati e verificare checksum, manifest e versioni delle dipendenze; non modificare il server di produzione senza decisione esplicita.
3. Eseguire inferenze vere per ciascun motore neurale DiffSinger, RVC, Seed-VC e Transkun, registrando input, output, log e metriche. Le fixture non valgono come inferenze.
4. Con audio etichettato, eseguire benchmark 10–16 strumenti reali senza assumere distinzione affidabile fra esecutori di timbro identico.
5. Eseguire prove browser/native, export, salvataggio/riapertura, GM FluidSynth/TinySoundFont, controller e ascolto.
6. Ripetere la regressione generale in un ambiente controllato e autorizzato, investigando l'eventuale richiesta GitHub senza bypassare i blocchi.

**Criterio di completamento:** niente difetti software aperti individuati dai test di accettazione e prove end-to-end documentate. Nuovi difetti implicheranno ancora sviluppo software.

## EN
Version remains 0.3.0-r210. Offline regression: 143 passed, 0 failed, 15 skipped; this does not certify all three macroareas. Review independent per-component licensing, install authorized runtimes and checksummed assets in a test environment, run genuine DiffSinger/RVC/Seed-VC/Transkun inference and labeled 10–16-instrument benchmarks, validate real GM, browser/native and project reopen workflows, and run a controlled full regression without bypassing prior GitHub network governance. Any uncovered defect still requires software development.
