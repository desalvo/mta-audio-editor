# Server MTA r208 — Pubblicazione Pages e predisposizione R2

## Stato e limiti

- La destinazione **attiva** rimane GitHub Pages tramite workflow artifact nel repository `desalvo/mta-audio-editor-packages`.
- **Ogni canale (`early`, `stable`) conserva al massimo le 2 versioni native più recenti per formato e architettura**. La retention viene applicata al payload pubblicato (non agli artifact GitHub Actions). Debian usa `dpkg --compare-versions`; RPM usa `rpm.labelCompare` tramite `python3-rpm`.
- Per un nuovo rilascio il publisher tenta di scaricare lo snapshot firmato precedente, ne verifica SHA-256, importa i vecchi pacchetti, seleziona le due versioni e rigenera/firma i metadati.
- NON elimina i vecchi artifact GH: sono soggetti alla retention nativa GitHub (90 giorni). Se l'artifact precedente è scaduto, la pubblicazione fallisce in sicurezza, anziché perdere silenziosamente una versione precedente. La conservazione di lungo periodo necessita R2 o altro storage persistente.
- Il sito Pages ha un limite documentato di circa 1 GB; il deployment ora lo controlla prima dell'upload.
- La retention di due versioni limita il numero di pacchetti nel repository **pubblicato**, non la somma dello spazio storico occupato da artifact CI, GitHub Releases o R2 non ripuliti.
- I pacchetti di differenti distribuzioni con lo stesso formato/architettura potrebbero richiedere repository distinti in futuro: la politica attuale corrisponde ai pacchetti nativi effettivamente costruiti dalla matrice.

## Installazione dei file nei due repository

1. Nel repository sorgente `desalvo/mta-audio-editor` eseguire un commit del nuovo cumulativo, inclusi `scripts/repositories/retain_channel_packages.py`, `restore_previous_channel.py` e `.github/workflows/server-pages-publish.yml`.
2. Nel repository `desalvo/mta-audio-editor-packages` aggiornare `.github/workflows/pages.yml` e `scripts/assemble_pages.py` dai corrispondenti file `packaging/pages-repository` del cumulativo.
3. Confermare Settings → Pages → Source = **GitHub Actions**, secret `MTA_SOURCE_ARTIFACT_TOKEN` con Actions read sul sorgente e environment di firma `server-early`/`server-stable` nel repository sorgente.
4. La pubblicazione va avviata su un run certificato della matrice **appartenente allo stesso commit**; il workflow corrente richiede un evento `push`. Se si cambia solo il publisher, è necessario adattare in un successivo intervento il gate della matrice per consentire `workflow_dispatch` autenticato e verificato, oppure fare un commit che avvii la matrice sui path monitorati.
5. Pubblicare `early`, verificare `InRelease`, `Release.gpg`, `repomd.xml.asc`, SHA e client APT/DNF prima di pubblicare `stable` con approvazione manuale.

## Cloudflare R2 (predisposto, DISATTIVATO)

Lo script `scripts/repositories/r2_publish.py` prepara l'upload S3-compatible del medesimo albero firmato in un bucket R2. È **dry-run per impostazione predefinita**, non viene richiamato dalla CI attuale ed è bloccato in modalità reale finché `MTA_R2_PUBLISH_ENABLED=true` non viene impostato esplicitamente.

Per l'attivazione futura, configurare in GitHub Environment protetto: credenziali R2 ad accesso limitato (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`), `MTA_R2_BUCKET`, `MTA_R2_ENDPOINT` con URL `https://<account-id>.r2.cloudflarestorage.com`; installare `boto3` e scegliere il dominio pubblico HTTPS per client APT/DNF. Usare gli stessi file metadata firmati e la stessa policy di due versioni.

Esempio dry-run, su un albero già firmato:

```bash
python scripts/repositories/r2_publish.py --root ./signed-tree --channel early
```

Esecuzione reale soltanto dopo revisione e configurazione di credenziali, bucket e domini:

```bash
MTA_R2_PUBLISH_ENABLED=true \
python scripts/repositories/r2_publish.py --root ./signed-tree --channel early \
  --bucket "$MTA_R2_BUCKET" --endpoint "$MTA_R2_ENDPOINT" --execute
```

**Non è ancora una migrazione R2 attivabile in produzione con un semplice switch**: prima occorrono verifica degli endpoint pubblici, firme remote, test APT/DNF dal dominio R2, cleanup transazionale degli oggetti non più referenziati e test di rollback su R2. Per ora il progetto mantiene Pages come sola destinazione attiva.
