# ChordFormer, UVR e DrumSep — verifica specifica 20/10/2026

Versione MTA **0.3.0-r210**. Il controllo `commercial-service` del pannello Studio governa **l'ammissione di modelli in `cost_recovery`**. Non interrompe automaticamente altri servizi, abbonamenti, fatturazioni o accessi API a pagamento: questi devono essere sospesi e collaudati separatamente prima di dichiarare l'istanza non commerciale. La doppia conferma è obbligatoria. Il default dei checkpoint senza prove resta `disabled`.

| Motore | Evidenze pubbliche | Decisione implementativa |
|---|---|---|
| ChordFormer (5 checkpoint) | Progetto `mwaseemrandhawa/ChordFormer` e fork adottato non stabiliscono chiaramente i diritti su ciascun file di pesi | Bloccato fino a prova riferita ai pesi esatti, hash e deployment; spegnere il commercio non crea un'autorizzazione |
| UVR `UVR_MDXNET_KARA_2.onnx` | README UVR invita ad attribuire il team e richiama MIT per i modelli, ma l'issue #2185 domanda espressamente conferma dei diritti su questo ONNX ed è aperta | Bloccato di default. Possibile attivazione con licenza verificata o autorizzazione dell'avente diritto per l'esatto checkpoint; no redistribuzione automatica prima della verifica |
| DrumSep | `inagoy/drumsep` è MIT; `splitzo/drumsep` pubblica ONNX e model card MIT, dichiara conversione dall'originale. Il mirror MTA `gridshiftstudio/drumsep-onnx` richiede ancora verifica di identità, hash e chain-of-title | Priorità a verifica della variante originale o conversione documentata; nessuna assunzione automatica di equivalenza dei checkpoint |

**Workaround ammessi:** scegliere un checkpoint alternativo con licenza verificata; ottenere autorizzazione scritta con evidenza conservata; eseguire solo nel contesto autenticamente non commerciale *quando la licenza effettiva del checkpoint lo consente*. La modalità gratuita non risolve una licenza sconosciuta. Il gestore deve garantire separazione operativa di abbonamenti, quote a pagamento, API e fatturazione: il solo interruttore MTA non basta.

**Test eseguiti:** controlli locali di ammissione e interruttore. **Non verificati:** browser reali, deployment finanziario completo, hardware ROCm e licenze giuridicamente confermate per i pesi ambigui.

**Fonti:** https://github.com/mwaseemrandhawa/ChordFormer ; https://github.com/Anjok07/ultimatevocalremovergui/blob/master/README.md ; https://github.com/Anjok07/ultimatevocalremovergui/issues/2185 ; https://github.com/inagoy/drumsep ; https://huggingface.co/splitzo/drumsep
