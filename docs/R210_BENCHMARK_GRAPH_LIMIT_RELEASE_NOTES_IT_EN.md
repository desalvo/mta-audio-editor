# r210 — benchmark graph cap / limite grafo benchmark

IT: Introdotto limite massimo di 1.000.000 di coppie candidate nel matching del benchmark Audio-to-MIDI. Il benchmark restituisce ValueError; non crea metriche incomplete o risultati fittizi. Invariata versione 0.3.0-r210. Test locali: 72 passed, 0 failed, 12 skipped. Rimangono regressione generale, prove di inferenza reale e collaudi di piattaforma.

EN: Added a maximum of 1,000,000 candidate note pairs to Audio-to-MIDI benchmark matching. An over-dense workload fails with ValueError rather than returning truncated or fabricated metrics. Version remains 0.3.0-r210. Local tests: 72 passed, 0 failed, 12 skipped. Full regression, real model inference and platform acceptance remain open.
