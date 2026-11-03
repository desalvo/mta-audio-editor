# Importazione di registrazioni reali per il benchmark

La sezione amministrativa **Benchmark e validazione AI** permette di importare un dataset ZIP. Il dataset può contenere uno o più casi reali, con il solo DRUMS oppure anche mix, riferimenti e componenti isolate. La mancanza di ground truth rimane esplicita e limita le metriche disponibili.

L'importazione richiede una dichiarazione esplicita dei diritti sull'audio. Questa registra l'identità dell'amministratore autenticato, la data e l'hash dell'archivio; **non** certifica automaticamente copyright, diritti dei modelli o qualità della separazione.

## Struttura

Il file manifest.json deve trovarsi alla radice. Sono ammessi soltanto questo file e i WAV registrati nel manifest, oltre alle loro directory. Un esempio minimo di caso senza ground truth è:

    {
      "schema": "mta-percussion-corpus-1",
      "id": "mie-registrazioni-v1",
      "name": "Registrazioni personali",
      "counts": {
        "declared": 1, "prepared": 1, "synthetic": 0,
        "negative": 0, "real": 1, "real_unavailable": 0
      },
      "cases": [{
        "id": "brano-uno",
        "title": "Registrazione acustica",
        "group": "real",
        "category": "acoustic",
        "prepared": true,
        "exact_ground_truth": false,
        "family_id": "registrazione-originale-uno",
        "split": "test",
        "duration_seconds": 12,
        "frames": 576000,
        "sample_rate": 48000,
        "channels": 2,
        "input_drums": "audio/drums.wav",
        "input_mix": null,
        "reference": null,
        "references": {},
        "mix_references": {},
        "sources": {},
        "rights": {
          "basis": "user_owned",
          "source": "Registrazione originale di mia proprieta, con i permessi necessari"
        },
        "sha256": {
          "audio/drums.wav": "SOSTITUIRE_CON_LO_SHA256_REALE_DI_64_CARATTERI"
        }
      }]
    }

L'esempio va completato con l'hash reale e con frame, frequenza e canali effettivi. Il server verifica tali dati leggendo il WAV. I file possono essere PCM interi o FLOAT; i campioni NaN/Inf, file corrotti o formati diversi rinominati con estensione WAV vengono rifiutati.

Per una registrazione usata sotto licenza, rights.basis deve essere licensed e devono essere presenti anche rights.license e rights.evidence, con identificazione della licenza e provenienza della relativa autorizzazione. È possibile conservare attribuzione e dettagli del permesso. Valori caricati come reviewed_by, verified o approvazioni non diventano autorità del server.

## Ground truth e categorie

Quando esistono componenti isolate, aggiungerle a sources (ad esempio snare, tom, hi_hat, cymbals, kick e percussion), registrando ogni file con il suo SHA-256. I riferimenti devono avere la stessa geometria e lo stesso allineamento dell'input.

references.include_kick ed references.exclude_kick indicano i riferimenti per DRUMS. Se il mix completo contiene percussioni assenti da DRUMS, usare separatamente mix_references.include_kick ed mix_references.exclude_kick. Non riutilizzare automaticamente un riferimento del mix per una sorgente che non contiene tutti gli eventi desiderati.

I segmenti e derivati della stessa registrazione devono mantenere lo stesso family_id e split. L'importatore rifiuta famiglie distribuite su split diversi e anche file con byte identici che attraversano split diversi, pur se dichiarati con famiglie differenti. Non viene dichiarato un riconoscimento automatico di tutte le trasformazioni o derivazioni acustiche.

## Protezioni e pubblicazione

- Limite: 256 MiB compressi, 512 MiB decompressi, 2048 voci ZIP.
- Nessun percorso assoluto, traversal, backslash, controllo Unicode o nome non canonico.
- Nessun symlink, file speciale, collisione maiuscole/minuscole, duplicato o conflitto file/directory.
- JSON senza chiavi duplicate o valori non finiti.
- File e checksum devono corrispondere esattamente alla registrazione del manifest.
- Un dataset esistente non viene sovrascritto, neppure se la sua directory è vuota.
- Il corpus viene validato in area privata e il manifest viene pubblicato per ultimo. Un fallimento pulisce soltanto la directory non pubblicata appartenente a quell'importazione.

L'API amministrativa è POST /api/admin/ai-benchmarks/datasets/import, con multipart file e acknowledge_rights=true. L'identità dell'attore proviene dalla sessione amministrativa, mai dal ZIP.

Le prove automatiche sono in tests/test_r210_percussion_dataset_import.py. I WAV delle fixture verificano il funzionamento dell'importatore e non costituiscono sei registrazioni realistiche aggiuntive o un benchmark neurale. I sei slot realistici del corpus iniziale rimangono indisponibili finché non vengono fornite registrazioni autorizzate e pertinenti.

