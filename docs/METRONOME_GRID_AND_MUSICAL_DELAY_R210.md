# Griglia metronomo indipendente e delay musicale — 0.3.0-r210

## Italiano

La barra orizzontale contiene **♩ Griglia** accanto al comando del metronomo. Questo comando modifica BPM e misura del solo metronomo senza modificare BPM audio, BPM di riferimento, tonalità, delay o posizioni delle tracce musicali. I controlli BPM del transport restano i controlli della velocità audio; il loro titolo lo indica esplicitamente.

- **Standard:** una griglia per l’intero brano, con BPM 20–400 e misura selezionabile. Si può configurare anche prima di creare il click. Il comando rigenera il click esistente e conserva il suo volume.
- **A zone:** BPM e misura per ciascuna zona delimitata dai marker. Aprire **Griglia** e scegliere una zona, oppure fare doppio click sull’etichetta della zona sulla traccia metronomo. È disponibile anche il menu contestuale. **Riporta in Auto** elimina le forzature della zona. Le impostazioni manuali usano gli identificativi dei marker e sopravvivono allo spostamento del loro timestamp e alla rigenerazione completa. Cambiare i valori globali della griglia aggiorna le zone non forzate e conserva quelle manuali.
- **Adattivo:** i controlli manuali della griglia sono disabilitati; rimangono analisi e sensibilità adattiva. Le vecchie impostazioni standard eventualmente salvate non sostituiscono la mappa rilevata.

Le misure disponibili sono 2/4, 3/4, 4/4, 5/4, 6/8, 7/8, 9/8 e 12/8. È mantenuta la convenzione MTA: il BPM conta gli impulsi udibili; il numeratore raggruppa gli impulsi in misure, il denominatore determina notazione e accenti. I metri composti in ottavi mantengono gli accenti secondari. La scelta della misura non moltiplica automaticamente la velocità dei click.

Snap, indicazione musicale del transport e conversione del delay usano la griglia del metronomo. Per le zone, la griglia riparte dal marker iniziale della zona; le posizioni musicali digitate sono relative alla zona corrente. Il pre-roll usa la griglia globale del metronomo, non il BPM che modifica la velocità audio.

Accanto al delay di ogni traccia è disponibile un selettore persistente:

| Unità | Esempio | Significato |
| --- | --- | --- |
| ms | -125 | Anticipo di 125 millisecondi |
| Beats | 2.5 | Ritardo di due impulsi e mezzo |
| Misure | 1.5 | Ritardo di una misura e mezza |
| Misure:Beats | -1:2 | Anticipo di una misura più due impulsi |

Il formato composto rappresenta una **durata da 0:0**, non una posizione da 1:1. In 4/4 a 120 BPM, `1:2` equivale a 3000 ms; `-0:2` equivale a -1000 ms. La parte beats deve essere minore del numeratore; sono ammesse frazioni di beat. Nel metronomo a zone la conversione usa BPM e misura alla posizione iniziale del segmento più anticipato della traccia. Il valore effettivo resta salvato in millisecondi: cambiare griglia o unità di visualizzazione non sposta di nuovo la traccia. Il dialogo contestuale del delay spiega la convenzione e mostra l’equivalente in ms.

Il formato del progetto conserva tutti i nuovi campi. I progetti precedenti continuano a usare BPM e misura già esistenti finché non viene impostata una griglia indipendente.

## English

Use **♩ Grid** on the horizontal toolbar to configure the metronome independently of audio playback speed. Transport BPM remains the audio speed control. Standard mode has one BPM/meter setting; zone mode has editable BPM and time signature per marker zone, including stable manual overrides and Auto reset. Global changes update unforced zones and retain manual settings. Adaptive mode is analysis-driven and does not accept manual grid overrides. Regeneration preserves musical audio, clip positions, pitch, audio tempo and the click track volume.

Per-track delay units are persistent: milliseconds, beats, bars and signed bars:beats durations. The compound format starts at `0:0`, with a beat remainder smaller than the meter numerator. At 120 BPM in 4/4, `1:2` is +3000 ms and `-0:2` is -1000 ms. Zone conversions use the grid at the earliest segment start. The canonical delay stays in milliseconds, so changing the grid or display unit does not change an existing delay. Snap and musical transport positions use the same metronome grid; zone positions restart at the zone boundary.

MTA retains its audible-pulse BPM convention: meter numerator groups clicks into bars and the denominator controls notation/accent patterns. Supported signatures are 2/4, 3/4, 4/4, 5/4, 6/8, 7/8, 9/8 and 12/8. Manual settings are 20–400 BPM. Legacy projects fall back to their existing tempo/meter until independent settings are configured.

## Validation

Targeted tests include byte-identical musical audio renders before/after grid changes, preserving an existing non-unity audio tempo ratio, actual zone PCM isolation and equality after full regeneration, manual meter persistence through marker moves, adaptive rejection, rollback and authorization, signed musical delay parsing and per-zone conversion, and legacy project persistence. Full regression results are under `validation/r210-grid-*`.

Installed Windows/macOS GUI tests and deployed-server listening tests remain to be performed; no production server was changed and no GPU billing certification is claimed.
