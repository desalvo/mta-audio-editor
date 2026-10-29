Aggiornamento28 ottobre2026: le allocazioni parziali multicapture e il replay originale sono ora implementati nel medesimo protocollo;leggere **PAYPAL_PARTIAL_SETTLEMENT_R210.md**. I limiti storici riportati sotto sono superati solo per quel percorso. A4/C3 e RC rimangono aperti.

# MTA 0.3.0-r210 — Recupero di chargeback difesi da report autenticati

28 ottobre 2026, Europe/Rome. **PRE-RC, 28/42 (66,7%), E completa 1/7. Nessun criterio originale promosso.** L'aumento numerico richiesto non è conseguito. La chiusura riguarda un percorso operativo preciso; A4/C3 non diventano completi per effetto di questo sottoinsieme.

Baseline confermata: `4c3c73afe6d3829aad155c23f5f1bbb6d375433a`, full CI40584085026 conservata per quella revisione. Il cumulativo precedente `MTA-0.3.0-r210-pre-RC-merchant-range-cumulative.zip`, SHA256 `7ba3bc15ad7acd4419a3af94809d23a5b0b24aaf94dbe5c3fc5a4a607d59f9fc`, è la base integra di questa consegna. Delta B5/drain/E4/F3/merchant ancora non committato. Nessun commit, staging, push, tag, dispatch CI o accesso a server/provider reali.

## Comportamento completato

Prima un caso risolto con payout e movimenti non univoci restava incerto anche se l'operatore disponeva di una prova supplementare. Ora esiste una procedura CLI distinta che può liberare l'hold quando tutte le prove del profilo coincidono: caso difeso S6 nel report ACM, credito principale completato T1202/T1205 nel report STL, stesso conto canonico e allocazione esatta per capture/caso. Nessun semplice importo, stato della disputa, file caricato dal browser o conferma amministrativa costituisce una quietanza.

Il protocollo acquisisce i due CSV soltanto da `reports.paypal.com`, mediante i percorsi fissi `/disputes/outgoing` e `/ppreports/outgoing`. Usa binari OpenSSH root-owned non scrivibili da gruppo/altri, host key obbligatorie fornite dall'operatore e copie private delle credenziali lette da descriptor con controllo di proprietà, modalità e symlink. Sono disabilitati configurazione SSH personale, agent, password, autenticazione interattiva/GSSAPI, proxy e multiplexing. I nomi remoti ammettono solo report singoli datati; nessun URL o comando arbitrario.

Ogni file è limitato a16MiB, con timeout di connessione15s e download90s; processo/gruppo raccolti con attesa limitata15s. Le copie temporanee sono eliminate. I CSV hanno limiti su righe/campi e controllo di header, conto, versione, intervallo, footer e conteggi. Per STL si ricontrollano i totali di principale e commissioni. Le commissioni non diventano credito del cliente. Nomi/email/note dei report non entrano nella ricevuta persistita.

La procedura usa la configurazione PayPal già esistente e richiede un ordine locale originale, amministratore attivo, ambiente live e merchant ID del payee restituito dall'API canonica. I report devono riguardare quel conto. Si ricontrollano ordine/owner/tipo/periodo/importo/configurazione, stato canonico, apertura e aggiornamento del caso, capture e importo. La data di apertura serve anche a non adottare un precedente caso riutilizzando un ID. Un report antecedente all'aggiornamento canonico non basta. Non vengono cercati abbinamenti per sola somiglianza di importo/data.

La piena rilettura di capture/rimborsi/dispute già esistente resta obbligatoria. Nella stessa transazione del ledger una claim immutabile assegna il movimento a un solo ordine/caso/capture/importo. Un riuso incompatibile fallisce. La ricevuta del rischio conserva hash dei file e documento canonico, identificativi, attore amministrativo e allocazione. La risoluzione può aggiornare soltanto un hold incerto coerente, mai annullare una perdita permanente o un esito terminale contrario.

Corretto un difetto reale del nuovo percorso: la prova supplementare dello stesso documento poteva liberare l'hold ma lasciare pendente la precedente osservazione incerta. Ora si chiude anche quella osservazione soltanto se il digest del documento coincide esattamente; un documento cambiato resta da verificare. Replay ordinario dello stesso documento mantiene la ricevuta originale senza un secondo accredito. Un errore dopo la modifica annulla claim e saldo insieme.

L'intera operazione e il download diretto sono posseduti dal protocollo C2. Un drain avviato durante l'operazione aspetta il completamento originale. Un errore sincrono con tutti i processi raccolti chiude l'attività; quiescenza del figlio sconosciuta conserva l'ammissione originale, senza certificare falso zero. Non esiste un nuovo endpoint pubblico o un'eccezione generale al drain.

## Uso e prerequisiti

Procedura POSIX/OpenSSH, esplicita e solo per un operatore autorizzato. Non è stata abilitata né eseguita contro un conto reale. Occorrono accesso ACM/STL approvato da PayPal, account SFTP separato, chiave privata e host key attendibili già provisionati. Non usare host key accettate alla cieca e non passare password/segreti nella riga di comando.

```bash
python scripts/reconcile_paypal_reports.py --actor ID_ADMIN --order-id ORDINE_LOCALE --username UTENTE_SFTP --key-file /percorso/chiave --known-hosts /percorso/known_hosts --acm-name ACM-20261025.01.006.CSV --stl-name STL-20261025.01.006.CSV --confirm
```

I file delle credenziali devono appartenere all'utente effettivo, essere privati, non symlink e non hardlink. La procedura legge dal provider: nessuna capture o refund viene inviata. Esegue modifiche locali al ledger solo dopo la verifica delle prove originali. Codici uscita:0 risoluzioni documentate senza revisione finanziaria pendente;2 prove non risolutive/obblighi ancora pendenti;1 errore con messaggio privato. Ripetere la stessa azione consente il recupero dopo una risposta persa senza doppio accredito. Se la quiescenza è sconosciuta, non rilanciare come un nuovo lavoro: conservare l'ammissione e verificare i processi originali.

Il profilo supportato è ristretto: CSV singolo/account singolo, EUR, versioni con struttura riconosciuta e contatori completi, stesso intervallo ACM/STL, stato S6 e credito principale T1202/T1205 con identità esatta e case ID corrispondente all'API. Parti mancanti, report MAM/multipart, altri stati, collegamenti indiretti, periodi diversi, valute diverse, prove vecchie e campi incompleti sono rifiutati o mantengono la revisione pendente. Non si dichiara che ogni conto PayPal disponga di questi report o di case ID interoperabili. Nessun requisito software di produzione aggiunto. I test del trasporto e dell’autorità POSIX dichiarano i prerequisiti su altri target;su questo Linux/OpenSSH tutti i46 nuovi casi passano senza skip.

## Evidenza e limiti di accettazione

`validation/r210/settlement-recovery-result.json`: **348 casi distinti passati,46 nuovi,zero errori/fallimenti/skip correnti**. La selezione ampia precedente da348 casi è riusata per i rami invariati;46 casi finali con audit dell’attore e61 gate finali sostituiscono gli stessi identificativi nell’aggregato. Include parser e rifiuti, trasporto isolato, account/contesto cambiati, rollback, replay, un solo uso del movimento e drain C2 reale. Il database/ledger applicativo e il protocollo di ammissione sono reali e isolati; API PayPal e processo SFTP sono sostituiti da fixture. **Non è una prova sul provider, sul formato effettivamente attivato per il conto o su una sessione SSH PayPal reale.**

Ruff completo app/native/tests/scripts e compilazione passano. Bandit:303 sorgenti,166 finding revisionati (0HIGH,21MEDIUM,145LOW):164 precedenti più due nuovi LOW B404/B603 revisionati per il trasporto fisso. Nessuna soppressione o modifica a checker/soglie. Ammissione:171 confini; inventario runtime:547 sorgenti/783punti. Il censimento Python HTTP resta30 siti/21file: il nuovo trasporto SSH è esplicitamente revisionato come confine di processo, non nascosto in quel conteggio. Nessuna nuova fullCI cumulativa o nuova accettazione Chromium dichiarata; UI/F3/axe invariate non rieseguite.

Le prime esecuzioni e il fallimento poi corretto rimangono negli XML storici. L’aggregato usa gli esiti più recenti per identità, non la somma delle riesecuzioni.

Fonti primarie confrontate: [ACM](https://developer.paypal.com/reports/acm), [Settlement](https://developer.paypal.com/reports/settlement/), [T-code](https://developer.paypal.com/reports/reference/t-codes/). Non derivare la quietanza dal solo T-code: la procedura pretende anche conto/caso/allocazione/documento canonico e completamento coerenti.

## Blocco esterno e ripresa

Non sono disponibili in questa sessione abilitazione e credenziali dei report, host key approvate o coppie reali ACM/STL del conto. Quindi resta aperta l'accettazione sul target. Nessuna autorizzazione a contattare provider/server reali è stata inferita. I residui non sono però tutti esterni: copertura integrale dello storico, riferimenti originali mancanti, altri payout/protection/formati/allocazioni e basi legacy quota/surplus richiedono ancora implementazione o prove. Questo profilo non completa A4/A5/C3/C5/D6.

Restano14 criteri originali: nove implementazione/diritti A4,A5,B2,C3,C5,C6,D6,F4,F6 e cinque target A6,B6,F5,G5,G6. Testo, peso e stato originali invariati. RC falsa e transizione finanziaria generale non autorizzata. Non tornare al collector o all'audit come nuovo lavoro: entrambi sono già consegnati. Proseguire sui casi finanziari generali e sulle basi originali legacy senza inventare debiti, quietanze o prezzi storici.

Cumulativo unico: MTA-0.3.0-r210-pre-RC-settlement-recovery-cumulative.zip. Tutti i file di ingresso,log originali,asset,manuali,licenze e metadati ZIP sono conservati. Nessun report reale,credenziale,modello o runtime incluso.

Commit cumulativo inglese suggerito,non eseguito:

`Complete guarded execution, administration and authenticated settlement recovery`
