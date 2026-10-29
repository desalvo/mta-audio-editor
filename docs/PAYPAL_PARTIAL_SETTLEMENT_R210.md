# MTA 0.3.0-r210 — Settlement parziali su più capture

28 ottobre 2026, Europe/Rome. **PRE-RC: 28/42 criteri originali (66,7%), E completa 1/7. Nessun criterio promosso; aumento numerico richiesto non raggiunto.** Questo checkpoint completa un percorso finanziario di A4, non l'intero storico PayPal né C3/C5/D6. RC falsa.

Ripresa dal cumulativo completo precedente `MTA-0.3.0-r210-pre-RC-settlement-recovery-cumulative.zip`, SHA256 `cacd281c095279b84600aa55b4ba9f552d9027ff9c2bf2c981eec531d039abde`, 4682 file. La copia locale era arretrata a23/42: è stata isolata e sostituita con l'archivio verificato prima di modificare il codice. Non ricominciare dalla vecchia cartella o da un precedente archivio. Baseline confermata `4c3c73afe6d3829aad155c23f5f1bbb6d375433a`; il delta cumulativo resta non committato. Nessuna modifica a GitHub, server, conto reale, modello, dipendenza o workflow.

## Risultato funzionale

Un caso da4EUR può riguardare due capture da3EUR e2EUR senza contenere importi per articolo. Prima il normalizzatore vedeva5EUR di lordo e rifiutava il caso prima di consultare la prova supplementare. Ora il report autenticato può assegnare esattamente2EUR alla prima capture e2EUR alla seconda. Non si dividono4EUR in proporzione ai lordi e non si ricostruisce un'allocazione da somiglianza di importo o data.

La prova richiede il medesimo caso, tutti e soli i suoi identificativi capture, lordo originale esatto, totale identico al documento canonico e un credito completato distinto per ogni allocazione. Restano obbligatori S6/ACM, T1202 o T1205/STL, conto canonico, date di apertura/aggiornamento/intervallo e tutte le verifiche del protocollo precedente. Un terzo riferimento dello stesso caso, una parte mancante o un importo nullo/contraddittorio sono rifiutati. Gli importi per articolo forniti dal provider hanno priorità: un report non può sostituirli quando sono incompleti o incoerenti.

L'acquisizione continua a usare soltanto il trasporto SFTP fisso e autenticato già consegnato. L'operatore deve essere un amministratore attivo e confermare esplicitamente; ordine/configurazione/account originali sono ricontrollati dentro la transazione finanziaria. Claim del movimento, hold e saldo vengono aggiornati nella medesima transazione. Un errore alla seconda capture annulla anche la prima, senza lasciare credito o movimenti parziali.

Il replay ordinario non richiede credenziali/report/admin attivo: conserva una decisione già applicata e la sua attribuzione originale. Deve però ritrovare la stessa impronta del documento canonico, ricevuta applicata con digest verificabile, ordine/capture/merchant, hold realmente rilasciati, claim immutabile del movimento e associazione del movimento allo stesso ordine. Le prove sono ricontrollate anche nella transazione monetaria: una claim eliminata tra discovery e commit impedisce il replay. Un documento cambiato non eredita allocazioni, permessi o quietanze. La revoca successiva del ruolo dell'amministratore non cancella una decisione storica; impedisce una nuova azione privilegiata. La lettura del journal è limitata al solo ordine originale e rifiuta oltre10000 eventi applicati, senza dichiarare completo un sottoinsieme troncato.

I rimborsi già avvenuti non sono riaccreditati dal rilascio. Nell'esempio, con3EUR rimborsati sulla prima capture, il saldo finale è2EUR, non5EUR. Per un abbonamento il wallet rimane zero e la quota rimborsata torna come esatto debito originale: nessuna duplicazione con il rischio rilasciato. Sono verificati sia il primo finanziamento sia l'ordine già pagato, con rimborso parziale o totale della capture.

## Procedura operativa

Stesso comando dell'handoff precedente, nessun nuovo endpoint o flag:

```bash
python scripts/reconcile_paypal_reports.py --actor ID_ADMIN --order-id ORDINE_LOCALE --username UTENTE_SFTP --key-file /percorso/chiave --known-hosts /percorso/known_hosts --acm-name ACM-20261025.01.006.CSV --stl-name STL-20261025.01.006.CSV --confirm
```

Richiede POSIX/OpenSSH, accesso ai report provisionato e host key attendibili già approvate. Chiave e known_hosts sono file privati dell'utente effettivo, non symlink/hardlink. Non fornire password/segreti nella riga di comando. Vedere `PAYPAL_SETTLEMENT_RECOVERY_R210.md` per timeout, limiti, trasporto e codici uscita0/2/1. Solo CSV singolo/account singolo/EUR con struttura supportata: multipart, altri stati/valute e collegamenti indiretti restano esclusi. Un file caricato, JSON con stato“pronto” o semplice conferma non è una fonte finanziaria. Dopo perdita della risposta usare la rilettura dell'ordine originale; non inviare una nuova capture o un nuovo refund. Su quiescenza sconosciuta restano le ammissioni e gli identificativi originali.

## Verifiche e riuso

**357 casi distinti passati,40 nuovi; zero fallimenti/errori/skip correnti.** `validation/r210/partial-report-result.json` identifica ogni caso e la provenienza dell'unione:283 interessati,86 finali che sostituiscono quelli sovrapposti,61 gate. Non sommare le riesecuzioni. Database,ledger,abbonamenti,rollback,concorrenza e corsa tra lettura/commit sono reali e isolati; API e report sono fixture. Nessun conto o trasporto PayPal reale è stato accettato.

Gitleaks8.24.3 con archivio verificato SHA256 esamina le righe testuali introdotte rispetto al cumulativo di ingresso:zero finding,configurazione/ignore invariate.

Il difetto del checkpoint precedente è riprodotto sul sorgente esatto dell'archivio: `partial-report-baseline-repro.json` registra il rifiuto precedente e le due allocazioni corrette correnti, su documenti sintetici senza denaro. Le prime sette asserzioni fallite del nuovo test negativo presupponevano erroneamente la presenza del journal dopo un rifiuto anticipato; la fixture è stata corretta. Gli XML originali rimangono. Non sono sette difetti economici e non vengono nascosti nel conteggio corrente.

Ruff completo app/native/tests/scripts e compilazione passano. Bandit completo303 sorgenti/166 finding,0HIGH/21MEDIUM/145LOW, tutti gli identificativi dei finding precedenti invariati. Nessuna nuova soppressione o eccezione. Inventari sorgenti aggiornati e checker invariati:171 confini C2,30 siti HTTP/21 file,547 sorgenti runtime/783 punti. Nessun nuovo trasporto/processo o nuova autorizzazione modello/UI. Si riusano fullCI40584085026 sulla baseline, Chromium/axe E4 e modello/HTTPS F3 invariati. Non si richiede una fullCI intermedia; la futura CI del commit cumulativo non è dichiarata eseguita.

## Residui e uscita del prossimo blocco

A4 rimane aperto per copertura completa del conto, riferimenti originali assenti, altri payout/protection/formati/valute/stati e validazione effettiva dei report. Accesso SFTP, host key approvate e coppie di report del conto non sono disponibili; nessun accesso reale è autorizzato. Non tutti i residui sono esterni: legacy quota/surplus e copertura finanziaria generale richiedono ancora codice/prove. Non rietichettare questi residui come accettati o sostituire i criteri originali con il sottoinsieme di questo comando.

Restano14 criteri: A4,A5,B2,C3,C5,C6,D6,F4,F6 di implementazione/diritti e A6,B6,F5,G5,G6 sul target. C3/C5/D6 non diventano abilitati per effetto di questi report; il profilo amministrativo ristretto conserva i propri rifiuti. Non ripetere collector, audit di copertura, bridge o questa allocazione come nuovo lavoro. Proseguire sulle basi originali legacy e sugli esiti finanziari non coperti; le prove indipendenti di diritti/esecutori restano attività parallele nella coda, senza delegazione automatica. Nessuna promessa di numero fisso di iterazioni può sostituire i criteri di uscita.

## Consegna cumulativa

MTA-0.3.0-r210-pre-RC-partial-settlement-cumulative.zip contiene tutti i file del precedente checkpoint, asset/manuali/licenze,616 log originali byte per byte, modi e attributi ZIP originali. Nuovo manifest completo e record di preservazione inclusi. Nessun DB runtime,cache,credenziale o modello aggiunto. Non è una release né una RC.

Commit inglese cumulativo suggerito,non eseguito:

`Complete guarded execution, administration and exact PayPal settlement recovery`
