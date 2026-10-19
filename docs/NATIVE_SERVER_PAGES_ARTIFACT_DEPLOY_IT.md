# MTA server: GitHub Pages senza il limite di 100 MiB per oggetto Git

## Correzione download bloccato — r210, 19 ottobre 2026

Il run `39265035765` ha passato 18m50s nello step di assemblaggio prima
che fosse annullato: `gh run download` era ancora attivo. Il successivo run
`39267934184` era nello stesso step al controllo. L'artifact sorgente
`12192119228` pesa 5.873.100.542 byte: include tutti gli RPM trattenuti,
che Pages scarta dopo il download. Non è dimostrato un guasto specifico di rete.

Il publisher conserva `signed-mta-pages-<canale>` per il ripristino delle
versioni precedenti, e produce in aggiunta `signed-mta-pages-site-<canale>`
con `pages-site.tar.gz`: contiene APT, chiave e indici RPM, senza binari RPM.
Il manifest conserva `sha256` del bundle completo e aggiunge `pages_sha256`
del bundle Pages. Nessun indice firmato viene modificato nel deploy.
Il controllo SHA usa memoria limitata. I download riportano l'attività ogni
30 secondi e terminano con errore esplicito dopo 1.200 secondi per canale;
il subprocess viene terminato e atteso. Restano i controlli di percorsi,
fingerprint, digest e dimensione complessiva del sito.

### Applicazione della correzione

1. Integrare il cumulativo nel repository sorgente e fare commit come di consueto.
2. Nel repository **desalvo/mta-audio-editor-packages**, copiare anche:
   - `packaging/pages-repository/.github/workflows/pages.yml` → `.github/workflows/pages.yml`;
   - `packaging/pages-repository/scripts/assemble_pages.py` → `scripts/assemble_pages.py`.
   Fare commit di entrambi i file. Il solo aggiornamento del sorgente non aggiorna
   automaticamente questi file nel repository packages.
3. Annullare i vecchi run packages ancora attivi se stanno scaricando il bundle
   precedente; la concorrenza serializzata farebbe attendere i nuovi run.
4. Dopo la CI/matrice server verde sul nuovo commit, eseguire nel sorgente
   `Publish signed server packages to GitHub Pages`, scegliendo il run della
   matrice dello stesso commit. Il nuovo publisher caricherà **entrambi** i bundle
   prima di aggiornare il manifest; non modificare a mano i checksum.
5. Controllare il nuovo deploy packages: deve apparire `Download signed-mta-pages-site-early`,
   poi verifica digest, estrazione, upload e deploy. Verificare infine i repository
   pubblici con APT/DNF e il controllo pubblico del publisher.

Rilanciare soltanto il vecchio deploy mantiene il download da circa 5,9 GB.
Per i manifest precedenti privi di `pages_sha256`, il nuovo assembler conserva
il percorso legacy, indicandolo esplicitamente. Se un nuovo bundle manca o ha
un digest errato, fallisce senza ripiegare silenziosamente sul legacy.
L'altro canale resta disponibile quando il relativo artifact non è scaduto;
per renderlo più leggero occorre ripubblicare anche quel canale.

## Architettura

I pacchetti server (.deb/.rpm) **non vengono più committati** nel repository `desalvo/mta-audio-editor-packages`.

1. Nel repository sorgente, il workflow manuale `.github/workflows/server-pages-publish.yml` verifica che il run della **Native server offline runtime matrix** corrisponda al commit corrente e sia `success`.
2. Dopo l'approvazione dell'environment `server-early` o `server-stable`, genera e verifica le firme GPG degli RPM e degli indici APT/DNF. Carica il bundle completo come `signed-mta-pages-<canale>` e quello destinato a Pages come `signed-mta-pages-site-<canale>` nel proprio run Actions.
3. Con la chiave SSH di deploy committa nel repository `desalvo/mta-audio-editor-packages` soltanto `manifests/early.json` o `manifests/stable.json`, con run ID, commit e checksum SHA-256 di entrambi i bundle.
4. Un workflow **nel repository dei pacchetti** scarica gli artifact firmati del repository sorgente per **entrambi** i canali presenti, ne controlla i checksum, verifica il fingerprint della chiave pubblica e pubblica l'intero sito usando `actions/upload-pages-artifact` e `actions/deploy-pages`.
5. Il sito finale resta `https://desalvo.github.io/mta-audio-editor-packages/`, con `apt/early`, `apt/stable`, `rpm/early`, `rpm/stable` e `mta-archive-key.asc`.

## Configurazione iniziale una tantum

1. Nel repository `desalvo/mta-audio-editor-packages`, creare il branch `main` (se vuoto, aggiungere README) e caricare dal cumulativo il file `packaging/pages-repository/.github/workflows/pages.yml` al percorso `.github/workflows/pages.yml`, e `packaging/pages-repository/scripts/assemble_pages.py` al percorso `scripts/assemble_pages.py`.
2. In `Settings > Pages` del repository **packages** selezionare **Build and deployment > Source: GitHub Actions** (NON `Deploy from a branch`).
3. In `Settings > Secrets and variables > Actions` del repository **packages**, configurare `MTA_SOURCE_ARTIFACT_TOKEN`, fine-grained PAT con accesso in **lettura agli Actions artifact** di `desalvo/mta-audio-editor` (`Actions: Read`). Non usare chiave privata GPG in questo repository: riceve solo artifact già firmati.
4. Nel repository **sorgente** mantenere gli environment protetti `server-early` e `server-stable`, con `MTA_GPG_PRIVATE_KEY`, `MTA_GPG_PASSPHRASE` e `MTA_PAGES_DEPLOY_KEY`. La corrispondente chiave pubblica SSH deve essere Deploy Key con scrittura nel repository **packages**. La chiave GPG pubblica deve avere fingerprint `0833A4FCB008ECAC9F98840B4C1D2DD95F5AEDB7`.
5. Dopo che la nuova CI è verde sul commit contenente questi workflow, eseguire `Publish signed server packages to GitHub Pages` in Actions del sorgente e indicare `verified_run_id` della matrice server dello **stesso commit**, con `channel=early` (per `stable` servono anche pacchetti non prerelease).
6. Verificare in `desalvo/mta-audio-editor-packages` il run `Deploy MTA package repositories to GitHub Pages`, l'URL Pages e i file firmati. Eseguire test reali APT e DNF dai repository pubblicati prima dell'uso in produzione.

## Vincoli e sicurezza

- Il limite Git di 100 MiB per singolo blob viene eliminato perché i pacchetti non passano da Git.
- **Non** sono eliminati i limiti GitHub Pages: dimensione totale del sito (circa 1 GB), limiti del servizio, dimensione e retention degli artifact Actions; GitHub Pages non è ideale per un catalogo crescente di release binarie. Quando il sito raggiungerà il limite, migrare i binari su storage/CDN mantenendo la firma degli indici.
- Il flusso usa manifest di due canali indipendenti; il sito viene ricostruito integralmente ad ogni deploy e non cancella l'altro canale finché il relativo artifact è accessibile.
- Gli artifact del publisher hanno retention 90 giorni: **per una produzione persistente non basta**. Prima di promettere disponibilità stabile, occorre archiviazione permanente dei bundle o replica in storage persistente; altrimenti un nuovo deploy dopo la scadenza del vecchio artifact può fallire. Questa implementazione è un primo rilascio per test della pubblicazione, non una garanzia di repository stabile nel lungo periodo.
- Il workflow del target scarica solo artifact da `desalvo/mta-audio-editor` e verifica manifest, SHA-256, percorsi dei file e fingerprint GPG. I client devono inoltre verificare le firme APT/DNF normalmente.
- La pubblicazione `stable` blocca pacchetti marcati early/dev; non converte artificialmente un pacchetto early in stable.
