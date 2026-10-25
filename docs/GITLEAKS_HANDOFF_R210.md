# Gitleaks compatibility and historical review — 2026-10-25

## Italiano

Base osservata: `37821a8f4089341023af8ba858ab5ae8c5648467`, con la precedente
patch Quality presente. Non è una dichiarazione di CI complessivamente verde.
Run e job interessati:
https://github.com/desalvo/mta-audio-editor/actions/runs/40193310151/job/121168933221

Il job supera Bandit e gli audit dipendenze, poi si ferma nella ricerca di credenziali.
Gitleaks8.24.3 rileva46 occorrenze storiche. Il precedente `[[allowlists]]`
globale non è la sintassi supportata da questa versione; richiede `[allowlist]`.
La patch mantiene tutte le regole predefinite e restringe l'eccezione già
prevista all'esatto hash pubblico estratto della tabella di trasporto MTA.

Tutte le46 occorrenze sono state verificate nei blob originali dei commit:

| Categoria | Occorrenze | Trattamento |
| --- | ---: | --- |
| Hash pubblici dei sorgenti nei manifest e nei report |29| Impronta storica esatta |
| Identificativi sintetici di richieste/idempotenza nei test |12| Impronta storica esatta |
| Credenziale generata da una fixture pytest in una authority temporanea |1| Impronta storica esatta |
| Segnaposto esplicito di un token nella documentazione |1| Impronta storica esatta |
| Password pubblica di un container localhost effimero di smoke test |1| Impronta storica esatta |
| Hash pubblico di integrità della tabella MTA |2| Valore esatto nell'allowlist compatibile |

Le44 impronte in `.gitleaksignore` legano **commit, percorso, regola e riga**.
Non vengono esclusi interi commit, cartelle, test, documenti o tipi di regole.
Il registro `docs/security/GITLEAKS_REVIEW_R210.json` conserva categoria,
motivazione e hash della regione originale per ciascun caso, senza ricopiare
valori di credenziali. Modifiche o nuove segnalazioni in commit successivi
richiedono una verifica nuova: questo registro non le approva automaticamente.

## Verifica effettuata

- Binario ufficiale Gitleaks8.24.3, scaricato dalla release e verificato con il
  checksum pubblicato dalla stessa release.
- Clone locale separato, nessuna scrittura remota; scansione del SHA e di tutti
  i riferimenti della CI: **329 commit, 232893629 byte**, come nel run originale.
  La configurazione precedente riproduce **le stesse46 impronte**,
  uscita2. Con la correzione, **zero segnalazioni**, uscita0.
- Controllo negativo con due nuove credenziali sintetiche in percorsi già
  presenti nella revisione: entrambe vengono rilevate, uscita2. Le eccezioni
  non costituiscono un'esclusione per percorso.
- Controllo aggiuntivo dei soli file consegnati, per verificare che la patch
  non introduca segnalazioni nuove. Esito nel report di validazione incluso.
- Nessuna suite unitaria o browser ripetuta: non sono modificati codice
  applicativo, dipendenze, workflow, soglie, scanner o regole di pubblicazione.

La cronologia non viene riscritta. I report originali restano invariati. Non
sono state trovate credenziali di produzione fra le46 occorrenze revisionate;
questa conclusione riguarda quelle occorrenze e non certifica altri ambienti.

## Applicazione

Scaricare la patch nella radice del repository:

```sh
git apply --check MTA-r210-gitleaks-history-fix.patch
git apply MTA-r210-gitleaks-history-fix.patch
```

Commit suggerito, successivo alla base indicata:

`Fix Gitleaks config compatibility and review historical non-secret findings`

Dopo il commit controllare **SAST and dependency audit** sul nuovo SHA e inviare
il link del job. Non serve il profilo browser completo per questa modifica.
Nessun commit, push, dispatch o modifica di GitHub/server è stato eseguito qui.
Nessun nuovo ZIP cumulativo. La conferma del job GitHub resta da acquisire;
**RC falsa, 23/42 criteri (54,8%), cambio di regime disabilitato**.

## English

The linked job fails in Gitleaks after Bandit and dependency audits. Its pinned
8.24.3 engine does not support the existing global array-style allowlist. The
patch uses the supported single global allowlist for one exact public digest,
plus44 reviewed historical fingerprints bound to commit/path/rule/line. All
default detector rules remain enabled; no whole path or commit is excluded.

The official checksum-verified engine reproduced the exact46 original findings
on the same history. The corrected scan returns0 findings/exit0. Two freshly
generated synthetic secrets in previously flagged paths are still blocked.
The per-finding audit contains rationale and original-region hashes, without
copying credential values. No unit/browser rerun or history rewrite occurred.
Apply the patch, commit it, and verify the new SAST job; no remote write or RC
claim was made here.

## Primary references

- Version-specific configuration and fingerprint documentation:
  https://github.com/gitleaks/gitleaks/blob/v8.24.3/README.md
- Official engine and checksum release:
  https://github.com/gitleaks/gitleaks/releases/tag/v8.24.3
- Original redacted SARIF artifact:
  https://github.com/desalvo/mta-audio-editor/actions/runs/40193310151/artifacts/12598333611
- Original artifact SHA256:
  `bceb313f6df5187a608e2b4cf417ccedf6771b487c95a836838d3e6cee0b0102`.
