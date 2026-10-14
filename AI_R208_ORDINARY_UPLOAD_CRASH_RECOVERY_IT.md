# MTA Audio Editor 0.3.0-r208 — Recupero upload ordinari dopo crash

## Ambito

Le rotte `POST /api/projects/{pid}/tracks` e `POST /api/projects/{pid}/tracks/{track_id}/replace` creano ora, sotto il lock cross-process del progetto, un journal `project/.ordinary-upload-pending.json` prima di creare i media. Il journal contiene snapshot dei nomi dei file `audio/` e `originals/`; la scrittura usa file temporaneo esclusivo, `fsync`, rename atomico e `fsync` della directory.

Quando il progetto viene salvato correttamente, la riconciliazione elimina solo nuovi media non referenziati nel progetto persistito; conserva audio referenziato e originali associati a una importazione confermata, quindi elimina il journal. Dopo un crash, la stessa riconciliazione si avvia automaticamente allo startup, per ogni progetto valido, sotto lock. Un nuovo upload riconcilia anche un eventuale journal residuo prima di iniziare.

Un journal corrotto o simbolico blocca il cleanup distruttivo e rimane per ispezione. I file preesistenti allo snapshot non vengono cancellati. La riconciliazione segnala eventuali errori di startup senza bloccare il resto del server.

## Limiti

Il journal attuale non copre tutti i writer, né realizza una transazione ACID condivisa con il filesystem. Gli originali non hanno una relazione persistente uno-a-uno con le tracce: perciò il recupero conserva tutti gli originali nuovi quando un upload è confermato. La protezione presuppone che tutti i writer concorrenti interessati rispettino il lock del progetto. La certificazione del crash reale su storage remoto e in ambiente multiprocesso rimane aperta.

## Test

Cinque nuovi test coprono pulizia dopo crash, commit preservato, journal danneggiato, journal symlink e rifiuto di sovrascrivere un journal non riconciliato. I test esistenti di rollback mockano la creazione del journal, mantenendo la verifica dei loro rispettivi errori. Suite locale r208: 966 passed, 9 warnings.
