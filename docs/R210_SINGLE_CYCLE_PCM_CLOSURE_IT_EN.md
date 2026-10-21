# r210 — Verifica trasversale e guardia PCM / Cross-area verification and PCM guard

## Italiano
- Corretto `app/vocal_conversion.py`: verifica dei campioni effettivi **dopo** il ricampionamento (che può introdurre overshoot), della sorgente dry e del mix finale prima della sostituzione WAV. Un segnale con NaN/infiniti, vuoto o con picchi oltre 1,01 è rifiutato.
- Aggiunti sei test dedicati, compresi NaN, infiniti, valori fuori gamma, campioni vuoti e PCM valido.
- Suite offline trasversale: **86 superati, 0 falliti, 4 saltati**, non è la regressione generale. Quattro skip: voicebank/core autorizzati ed `espeakng_loader` non installati. Log `validation/r210-single-cycle-closure-tests.log`.
- AI Vocal Studio, AI Multi-Track Audio-to-MIDI e General MIDI: nessuna certificazione di inferenze con checkpoint reali, accuratezza musicale 10–16 strumenti, collaudi reali/browser/native o regressione globale. Eventuali incompatibilità richiederanno codice aggiuntivo. Restano obbligatorie licenze separate di codice, checkpoint, voicebank, vocoder, ausiliari e SoundFont.
- Nessun intervento sul server, nessuna operazione Git e versione invariata 0.3.0-r210.

## English
- `app/vocal_conversion.py` now validates actual PCM **after** sample-rate conversion (which can overshoot), the dry input and final blended samples before WAV replacement, rejecting NaNs, infinities, empty arrays and peaks over 1.01.
- Six dedicated regression cases added, including non-finite, over-limit and valid samples.
- Offline cross-area suite: **86 passed, 0 failed, 4 skipped**, not the full repository regression. Skips: reviewed bank/core and missing `espeakng_loader`. See `validation/r210-single-cycle-closure-tests.log`.
- Real checkpoint inference, 10–16-instrument accuracy, real hardware/browser/native acceptance and full regression remain uncertified. Compatibility issues may require further development. Independent license reviews apply to source code, checkpoints, banks, vocoders, auxiliaries and SoundFonts.
- No Git or production server operation; version remains 0.3.0-r210.
