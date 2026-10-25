# Quality CI: correction and opt-in complete validation — 2026-10-25

## Stato e base

Base committata dall'utente: `2f7f8ead0dd5b331f8c0b142d13ca06e132b9011`.
Lo storico merchant Chromium è verde nel run `40188436190`; questo non significa
che la CI generale sia verde. Il job Quality del run seguente è fallito:

https://github.com/desalvo/mta-audio-editor/actions/runs/40188363093/job/121153872431

Report originale scaricato e verificato: **41 failed, 6400 passed, 104 skipped**,
1547,55 secondi; coverage **75,80%**, sopra la soglia richiesta del 70%.
ZIP diagnostico SHA256:
`a51252e8b24de4ea1aca7f6b95dbcc3a45fed0423ad83b071a83bafe6856ef93`.

## Correzioni

- Il runner Quality forza `MTA_ALLOW_INSECURE_NO_AUTH=false`. Il bypass globale
  precedente sostituiva anche le sessioni valide con l'utente di sviluppo id0,
  alterando prove di autenticazione, pagine account e recuperi economici.
  I singoli test possono ancora scegliere esplicitamente il proprio contesto.
- La prova dei replay HTTP configura il nuovo guard dell'esecutore prima di
  verificare il vero conflitto 409; non aggira il controllo nei prodotti.
- Il contratto IO verifica il resolver del namespace e i contatori fisici del
  singolo processo; il guard di provenienza include il percorso remote-worker
  già implementato e verificato nelle suite dedicate.
- Stub DOM aggiornato per `setAttribute`; verifiche dei tag script indipendenti
  dal parametro di cache, mantenendo il controllo del vero percorso montato.
- Il test NC riattende il form ricostruito e reinserisce i dati prima della
  seconda conferma. Il test di nuovo acquisto accetta esplicitamente la
  conferma checkout richiesta dall'interfaccia. Il mock subscription include
  la nuova lettura del regime, senza contattare provider reali.
- Le impronte dei trasporti usano campi AST serializzati in JSON, evitando la
  presentazione variabile di `ast.dump` fra versioni Python. Tutti i 30 confini,
  i 21 file, le posizioni, i nomi e gli SHA dei sorgenti applicativi coincidono
  col precedente inventario: aggiornati solo formato delle impronte e SHA del
  checker, conservando motivazioni e disposizioni. Nessuna soppressione.
  Un digest di riferimento controlla il formato anche nei successivi runtime.

Nessuna modifica al codice applicativo, ai pagamenti o ai controlli di sicurezza
di produzione. Le modifiche ai workflow e agli script di test sono autorizzate
dalla richiesta dell'utente di correggere Quality e ridurre la durata della CI.

## CI ordinaria e completa

`scripts/run_quality_tests.py` seleziona l'albero Python con due profili:

| Profilo | Quando | Selezione |
| --- | --- | --- |
| `unit` | Push e PR ordinari; dispatch senza input | Tutti i moduli che non importano Playwright |
| `full` | Dispatch con `full_validation=true`; push con `[full-ci]` nel messaggio; ogni tag `v…` | Intero albero di test, Chromium e runtime VST3 compresi |

La selezione ricorsiva comprende `test_*.py` e `*_test.py`. Sono rinviati moduli
interi: eventuali controlli API o statici contenuti nei moduli browser viaggiano
con essi. I controlli dedicati di autenticazione, billing, ledger, privacy,
ownership, inventario trasporti e subprocess restano nella suite ordinaria.
I moduli rinviati sono elencati uno per uno in `quality-test-selection.json`,
caricato anche se il job fallisce. Non sono dichiarati superati né coperti.
Il normale `pytest` senza questo runner continua a selezionare l'intero albero.

La soglia coverage resta **70% in entrambi i profili**, senza cambiare gli omit.
Ruff, compile, audit, build nativa VST3, controlli FFmpeg e gli altri job restano
attivi. Chromium viene installato solo nel profilo completo. Le pubblicazioni
Docker/main ed early-main richiedono inoltre Quality riuscita nel profilo completo:
un run rapido non le sblocca. Un push main con `[full-ci]` richiede la verifica
completa e può proseguire nelle pubblicazioni già previste dal workflow. Il
dispatch manuale valida ma non aggiunge pubblicazioni. I tag mantengono i gate
completi. Nessuna pubblicazione viene eseguita da questa sessione.

Nel precedente run i 31 moduli Playwright, 327 casi, occupavano **1090,21 s**
dei tempi misurati per caso; i rimanenti 6218 casi **426,22 s**. La nuova prova
MIDI aggiunge un modulo browser. Questi numeri spiegano il risparmio atteso,
ma non garantiscono un tempo GitHub: dipendono da runner, installazione e test.

## Verifica locale

- Prima esecuzione ampia del profilo unit: **6093 passed, 126 skipped**,
  603,15 secondi, coverage **73,71%**. Un caso aggiuntivo falliva perché mancava
  `cmake` nell'ambiente locale. Installato il prerequisito, rieseguito soltanto
  quel caso: **1 passed**. Il primo XML resta conservato con il suo errore,
  insieme al report separato della risoluzione; nessuna riscrittura in verde.
- I 126 skip restano prerequisiti non verificati, compresi runtime nativi e
  target opzionali. La CI conserva la compilazione VST3 e può eseguire casi che
  qui non avevano il relativo runtime. Python locale3.12.14; CI ancora3.14.
- **34 casi browser** account/worker/checkout/subscription passano in39,63s.
- Nuova prova sulla pagina MIDI e sulle API reali: **1 passed**; nota64,
  durata1500ms verificate nella bozza, risposta API, pagina e progetto salvato.
- Gate/profili/inventario/fixture: **43 controlli mirati passed**; i controlli
  finali del profilo e del digest AST sono passati dopo l'ultima modifica.
  Questi conteggi si sovrappongono alla suite ampia e non vanno sommati.
- Ruff completo e compilazione dei file Python modificati riusciti.

**Limite ancora aperto:** il singolo test combinato live VST3/HTTP/MIDI del run
originale non è stato riprodotto integralmente con il runtime host modificato
e il plugin nativo. La porzione MIDI isolata sulla pagina vera passa. Il test
combinato conserva tutte le aspettative e ora controlla e mostra le note della
bozza e della risposta API prima dell'attesa: nessun fallimento viene nascosto
spostandolo nella selezione completa. Serve la prima CI completa sul nuovo SHA.

## Applicazione e prossima esecuzione

Scaricare `MTA-r210-quality-ci-fix.patch` nella radice del repository:

```sh
git apply --check MTA-r210-quality-ci-fix.patch
git apply MTA-r210-quality-ci-fix.patch
```

Commit suggerito, solo modifiche successive alla base indicata:

`Fix Quality regressions and make full browser validation opt-in`

Dopo il commit il push esegue la suite ordinaria. Per questa prima validazione
avviare anche **CI / Production image** con **full_validation=true** e inviare
il link del job Quality. Non rieseguire il vecchio SHA. Il profilo completo
resta necessario prima della RC e per modifiche a UI, template, browser test,
MIDI, playback, VST3 o ai confini di integrazione interessati. Il workflow
specializzato merchant resta disponibile; la sua sola riuscita non sostituisce
la regressione completa. I tag di release selezionano automaticamente `full`.

Nessun commit/push/dispatch o modifica di GitHub/server è stato eseguito qui.
Nessun nuovo ZIP cumulativo. **23/42 criteri (54,8%), 0/7 macroaree; RC falsa,
cambio di regime disabilitato**. La correzione CI non chiude criteri funzionali.
Report locali: `docs/validation/r210/quality-ci-fix-result.json` e relativa
directory `quality-ci-fix/` nel checkpoint di lavoro. I log grandi non vengono
duplicati nella patch ridotta; l'originale rimane negli artefatti del run.

## English

The linked Quality run failed41 cases while reaching75.80% coverage. This patch
fixes reproduced test-context/fixture failures, removes the global CI auth
bypass, and makes transport fingerprints independent of AST pretty-printing.
Application sources and production security/payment behavior are unchanged.

Ordinary push/PR Quality runs retain every non-Playwright module, native build,
security checks and the unchanged70% coverage gate. Whole Playwright modules
are explicitly listed as deferred. Manual `full_validation=true` and release
tags select the complete tree with Chromium. A push message containing `[full-ci]`
also selects full validation. Main/Docker publishing additionally requires a
successful full-scope Quality job; a fast pass cannot unlock publication. Manual
dispatch does not add publishing. Plain pytest remains unchanged.
The prior browser group accounted for18min of measured test time; local unit
selection took10min and reached73.71% coverage, with prerequisite skips recorded.

Apply the patch and commit, then perform one complete CI dispatch on the new
SHA. The remaining live VST3 combined test needs that native-runtime check;
its MIDI portion passes in an independent real-page/API regression and its
diagnostics are strengthened. No full CI success or RC is claimed by this patch.
