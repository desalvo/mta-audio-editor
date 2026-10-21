# IT — Attivazione manuale di modelli soggetti a restrizioni (r210)

I motori restano disponibili nel catalogo, ma non vengono attivati per i checkpoint con diritti incerti. Un gestore può attivarli soltanto dopo aver verificato una licenza applicabile al **file esatto, ai pesi, all'uso sul server e alla modalità di erogazione**, oppure ottenuto un permesso scritto. L'assunzione di responsabilità e due conferme **non concedono né sostituiscono** tali diritti. La voce «ambiente non commerciale» richiede un utilizzo realmente non commerciale; un servizio gratuito all'interno di un'attività commerciale non è automaticamente qualificato.

In Impostazioni amministratore → Studio → Licenze: selezionare `free_only` oppure `cost_recovery` soltanto se consentito, registrare fonte HTTPS, motivo e titolo autorizzativo, spuntare la dichiarazione e completare due conferme distinte. Anche le API impongono titolo e doppia attestazione per i checkpoint soggetti a restrizioni. Gli eventi sono storicizzati. `free_only` continua a misurare consumi CPU/GPU senza fatturazione; non usare crediti, quote commerciali o abbonamenti per quei job. Si mantengono invariati metering e isolamento.

**Stato:** implementato e testato localmente per l'interfaccia di consenso a livello sorgente, policy API e test billing simulati; non certificato su browser reali, desktop native o server di produzione. Nessuna riabilitazione predefinita di Madmom, ChordFormer, UVR KARA 2 o DrumSep; servono evidenze sui checkpoint esatti. Non è una consulenza legale.

# EN — Restricted model manual activation (r210)

Restricted engines remain catalogued but unknown-rights checkpoints are **disabled by default**. Operators may activate one only with a verified license covering the **specific file, weights, server deployment and intended use**, or specific written permission. Assuming responsibility and clicking twice **do not grant permission**. A genuinely noncommercial deployment is not equivalent to a free service provided by a commercial operation.

In Admin Settings → Studio → Licenses select a permitted billing mode, provide the HTTPS evidence, detailed reason and authorization basis, accept operator responsibility and confirm twice. The API also checks the second confirmation and authorization basis; attestations are historized. `free_only` tracks CPU/GPU usage but does not charge for the inference. Metering and isolation are unchanged.

**Status:** local unit/integration tests pass; end-to-end production and native/browser validation remains open. Madmom, ChordFormer, UVR KARA 2 and DrumSep checkpoints remain disabled by default pending exact-checkpoint evidence. This is not legal advice.
