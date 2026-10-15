# Importazione WAV riscoperti senza journal locale — 0.3.0-r208

La finestra delle impostazioni dei worker AI remoti consente ora di selezionare esplicitamente il progetto aperto come destinazione di un risultato WAV riscoperto sul server. La nuova operazione `POST /api/native/ai-workers/remote-history/{kind}/import-wav/{request_id}/{pid}` non avvia inferenze, non inventa journal locali e non effettua addebiti. È distinta dallo scaricamento in sola lettura.

La procedura applica l'autorizzazione locale del progetto, usa la configurazione HTTPS/token privato del worker scelto, interroga direttamente lo stato server della richiesta completata (proprietà verificata mediante token) e legge l'artifact remoto tramite il percorso di validazione esistente. Accetta esclusivamente WAV PCM validati (`_verify_wav_bytes`), applica un lock di pubblicazione per progetto e impedisce l'importazione ripetuta tramite il nome contenente l'identificativo completo della richiesta. L'operatore deve aprire un progetto e confermare esplicitamente l'importazione.

## Confini della certificazione

L'associazione al progetto è una *scelta esplicita dell'operatore*: senza journal locale il server non può dimostrare a quale progetto apparteneva originariamente la richiesta. Un token condiviso fra adapter diversi non costituisce prova crittografica del tipo di worker originario: l'importazione è pertanto limitata a un WAV verificato e non modifica testi, accordi o gruppi di stem. Questi ultimi richiedono un contratto persistente server-side di attribuzione di adapter/progetto prima di poter essere importati automaticamente.

I test simulano lo stato remoto e il download in memoria; rimangono esclusi i collaudi GPU fisici, le build di installer nativi e i test su infrastrutture esterne. Versione e revisione non sono state modificate.
