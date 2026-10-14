# MTA Audio Editor 0.3.0-r208 — remote metering operator keyring

## Integrazione

- Configurazione facoltativa `MTA_AI_REMOTE_METERING_KEYS_JSON`: oggetto JSON che associa identificativi di chiave a segreti esadecimali minuscoli (almeno 32 byte, massimo 128 byte).
- La configurazione viene riletta a ogni verifica: rimuovere un ID revoca immediatamente l'accettazione delle future attestazioni firmate con quell'ID.
- Nessun fallback su v1, nessuna chiave predefinita e nessuna esposizione dei segreti nella diagnostica amministrativa `/api/admin/ai-billing/remote-metering-keys/status`.
- `ai_metering_bridge.capture_operator_authenticated_remote` verifica l'attestazione v2 usando solo la keyring dell'operatore e registra la misura CPU tramite l'interfaccia di evidence persistente esistente.
- Rifiuto di chiavi duplicate, ID ambigui, segreti deboli, configurazioni fuori dimensione e firme/identità discordanti.

## Verifica

Suite r208: 720 test superati, inclusi 102 nuovi test parametrizzati o di integrazione del confine del registro chiavi.

## Limiti

Il numero di test non rappresenta 102 funzionalità indipendenti. La funzione di acquisizione è predisposta per l'uso da un endpoint autenticato, ma il trasporto automatico end-to-end dal worker di inferenza verso il gateway non è ancora collegato. La firma autentica le asserzioni CPU/I/O del worker, NON certifica misurazioni GPU hardware per singolo job. Prima della dichiarazione di completamento software servono l'integrazione degli endpoint, la policy di autorizzazione del worker, la certificazione crash/recovery e le prove reali su ROCm.

Nessun commit, push, modifica al CT 130 o aumento della revisione.
