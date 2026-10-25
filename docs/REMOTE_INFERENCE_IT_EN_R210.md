# Inferenza remota / Remote inference — r210

## IT

Nelle impostazioni native aprire AI local / remote workers. Il messaggio sopra i motori distingue la connessione configurata dal permesso di eseguire un modello. Nel regime non commerciale ogni nuova richiesta richiede comunque la verifica dei diritti del modello scelto. Se il regime non è verificabile, l’invio resta bloccato. I token salvati non vengono mostrati.

Nel regime commerciale l’inferenza remota resta bloccata finché manca la verifica autenticata dell’identità e dei diritti del modello effettivamente eseguito. Un modello autorizzato localmente, un token valido, la firma delle misure o una connessione riuscita non sostituiscono questa prova. Lo stesso vale per l’adattatore HTTP ACE-Step su localhost o attraverso un tunnel: l’indirizzo non identifica il checkpoint. Non esiste un’opzione di forzatura.

È ancora possibile consultare e recuperare richieste precedenti o chiederne la cancellazione con le credenziali del proprietario. Queste azioni non avviano automaticamente una nuova inferenza e non provano che un worker remoto si sia fermato fisicamente. Un errore non avvia un modello locale come ripiego. Per l’autorizzazione del dispositivo usare Collega account: i percorsi riservati all’accesso non inoltrano richieste di inferenza.

Il controllo vale anche per le chiamate dirette e per l’adattatore avviato come processo separato. Gli ambienti separati del worker devono poter importare la policy dell’applicazione installata; se manca, l’esecuzione fallisce in modo conservativo. Il normale adattatore locale non commerciale è stato verificato con server HTTP temporanei di test. I controlli non concedono diritti mancanti e non pubblicano condizioni legali nuove.

## EN

Open native settings → AI local / remote workers. The note above the engines separates a configured connection from permission to execute a model. In non-commercial service every new request still requires the selected model's rights check. An unverifiable regime blocks submission. Saved tokens are never displayed.

Commercial remote inference remains blocked until authenticated identity and rights of the actual executing model are verified. A locally authorized model, valid token, metering signature or successful connection is not that proof. This includes ACE-Step HTTP on localhost or through a tunnel: the address is not checkpoint identity. There is no force-enable option.

Previous requests can still be inspected/recovered or cancellation requested with owner credentials. These operations do not automatically start a new inference and do not prove physical remote-worker termination. Errors never trigger automatic local inference fallback. Use Connect account for device authorization; those credential-only paths cannot forward inference requests.

The checks also apply to direct library calls and the standalone HTTP adapter. Separate worker environments must be able to import the installed application policy; missing policy dependencies fail closed. Normal non-commercial local adapter execution was tested against temporary local HTTP fixtures. These controls grant no missing rights and publish no new legal terms.

## Acceptance / Accettazione

The executing-checkpoint attestation protocol, complete opaque/native executor coverage, all installed checkpoint rights, real model/OS/GPU environments and the other release criteria remain open. No real remote model server was used. RC not reached; service-regime switching disabled. Current technical handoff: REMOTE_RIGHTS_HANDOFF_R210.md.
