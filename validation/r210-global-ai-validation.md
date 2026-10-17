# Validazione — 0.3.0-r210, coda globale e prove GPU

Base cumulativa: MTA-r210-media-stems-cleanup.zip, 1507 file, SHA-256
0ee46273bced167ee40e6c2da7289b7db9693acfa14dd8eff77960dbf29255f4.
Conservati tutti i file della base; 33 file aggiornati e 20 aggiunti.
Versione e revisione invariate. Nessun commit/push/tag/release o accesso al server.

## Esiti definitivi

JUnit completo: 3452 passed, 4 skipped,
0 failures, 0 errors; 10 deselected (AF_UNIX).
Tempo: 194.10 s. Copertura app: 77.72%, soglia 70% superata.
Gruppo mirato finale: 130 passed; log e JUnit inclusi.
Ruff app/native/tests e i due nuovi helper: superato.
compileall app/helper, Node --check app.js, bash -n build RPM/DEB: superati.
CLI status non configurata: exit 2, ready false, nessuna abilitazione implicita.
CRC e confronto byte per byte dell'archivio eseguiti dal confezionatore.

La regressione completa usa MTA_ALLOW_INSECURE_NO_AUTH=true per i test del
percorso locale/development preesistente. I test di autenticazione e quelli nuovi
rimuovono esplicitamente questa opzione quando provano la produzione, utilizzando
utenti/token isolati, HTTP reale di TestClient e processi worker di prova.
I 4 skip riguardano SDK opzionali assenti; le 10 esclusioni AF_UNIX sono le stesse
restrizioni del runner dei cumulativi precedenti, non sono test superati.

Le prove mirate coprono ammissione FIFO web/remota e riuso dello slot, cancellazione
in coda, recupero degli orfani, registrazione futura controllata, markers e opzioni
chords, ricevuta risorse con ACL per token, metadati WAV per la pubblicazione,
configurazione atomica privata e fallimenti senza modifiche, gate RPM/DEB,
regressioni import/media/stems e notifiche/accounting delle consegne precedenti.

I test GPU usano tracce sintetiche e firme di prova: unione degli intervalli,
controlli esclusi, zero verificato, mancanza di dispatch/kernel, duplicati, graph,
eventi persi, thread/dispositivo diverso, timestamp errati, firma/policy invalida,
prova scaduta o riutilizzata, segmenti incompleti/sovrapposti, assenza di retry
successivo al fallimento del profiler e fattura CPU+GPU idempotente. Non sono
una prova sul kernel/GPU AMD. Non è stata eseguita una calibrazione hardware.

I passaggi intermedi hanno trovato fixture obsolete per il nuovo contratto e
una race del callback di cancellazione, corretti prima dei risultati definitivi.
Un passaggio durante modifiche ai file ha invalidato le prove basate su
inspect.getsource; il passaggio finale è stato eseguito su sorgenti immutati.

## Limiti e validazione restante

Leggere SERVER_GLOBAL_AI_GPU_BILLING_R210.md. Billing software integrato per prove
calibrate valide, con tariffe e policy utente esistenti. Nessuna tariffa inventata
o attivazione sul server reale. Serve calibrazione nel medesimo ambiente ACE,
confronto con riferimento hardware e prove brevi/lunghe/cancellazione/concorrenza.
GPU ONNX/CLI esterne non ancora coperte dal provider continuo: restano non
fatturabili. Nessuna dichiarazione di certificazione completa del server.
La CPU del client HTTP ACE non rappresenta il consumo totale del servizio ACE.
RPM reale, build Windows/macOS, SMTP e browser/server di produzione non eseguiti.

## Messaggio Git cumulativo suggerito

Unify queued AI engines, native setup and tokens, usage notifications and calibrated GPU billing; fix media workflows
