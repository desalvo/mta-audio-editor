# r208 — Identità del runner e recupero dopo riavvio

La coda SQLite distingue ora un runner attivo usando, su Linux, la coppia boot ID e start tick del processo (/proc/PID/stat). Il PID da solo non è affidabile perché può essere riutilizzato. Lo schema esistente viene migrato automaticamente con la colonna `runner_identity`.

Un job il cui runner non corrisponde più all'identità registrata viene marcato `interrupted`; non è rieseguito automaticamente perché gli attuali callback Python non sono payload serializzati idempotenti. I job legacy senza identità continuano a usare il controllo PID per compatibilità con database esistenti. La correzione non equivale a restart recovery con replay e non certifica l'instradamento di tutti gli adapter nella stessa coda.

Verifiche: 8 test locali mirati superati, incluso database legacy e falso positivo per riutilizzo del PID. Quality completa e inferenza ROCm non eseguite.
