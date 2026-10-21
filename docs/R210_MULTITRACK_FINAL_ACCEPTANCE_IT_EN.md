# Multi-instrument accuracy acceptance / Accettazione accuratezza multistrumento

## Italiano

**Stato: NON CERTIFICATO.** La trascrizione reale MR-MT3 su AMD ROCm è completata (122/122 finestre) ma rimane largamente sotto l'obiettivo di accuratezza su 10–16 strumenti. Sul MIDI e audio Merish5 originali, il confronto rigoroso a offset zero produce 925 corrispondenze su 8.853 note previste e 10.632 note di riferimento, F1 = 0,0949448293559148. Soltanto **due programmi melodici** hanno almeno una corrispondenza completa di programma, pitch, onset e offset. Questo conteggio è una condizione necessaria debole, non prova di qualità.

Nuovo strumento: `scripts/audit_multitrack_acceptance.py` consuma il rapporto del valutatore `scripts/compare_multitrack_models.py`, richiede identità del protocollo a soglie invariate e produce un audit JSON con codice 2 di non certificazione. Non importa automaticamente un nuovo modello, non esegue inferenza e non adatta i risultati alle note MIDI attese. La versione 0.3.0-r210 è invariata.

Per arrivare alla chiusura occorre ottenere checkpoint/runtime YourMT3+ verificati, eseguire inferenza indipendente sulla medesima registrazione, confrontare strumenti e note con soglie di accuratezza già approvate, ripetere su un insieme rappresentativo di mix multistrumento non utilizzato per calibrare algoritmi e correggere i problemi effettivi di modello/postprocessing. Non attribuire ai soli test hardware ciò che resta un problema di accuratezza del modello.

## English

**Status: NOT CERTIFIED.** Real AMD ROCm MR-MT3 inference completed 122/122 windows, but strict zero-offset matching of the Merish5 song yields 925 matched notes out of 8,853 predictions and 10,632 reference notes, F1 = 0.0949448293559148. Only **two melodic GM programs** have even one strict program/pitch/onset/offset matched note. This is a weak necessary condition, not a sufficient accuracy target.

New `scripts/audit_multitrack_acceptance.py` consumes fixed-protocol `compare_multitrack_models.py` output, validates the protocol and instrument evidence, and exits 2 with a non-certification JSON record. It does not run neural inference, fit offsets to ground truth, relax acceptance tolerances, or assert model accuracy. Version 0.3.0-r210 unchanged.

Closure requires separately licensed and hash-verified YourMT3+ weights/runtime, independent same-audio neural output, preset quality acceptance criteria, out-of-sample representative multitrack benchmarks, and software/model remediation of measured errors. Hardware execution alone is not sufficient.
