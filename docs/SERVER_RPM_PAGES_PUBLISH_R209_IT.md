# Server RPM r209: GitHub Pages con pubblicazione dei binari esterna

La pipeline `server-pages-publish.yml` usa due destinazioni:

1. **GitHub Releases**, tag `server-packages-early` o `server-packages-stable`: contiene i file `.rpm` firmati (EL9 ed EL10), anche quando superano i 100 MiB consentiti a un singolo blob Git.
2. **GitHub Pages** (`desalvo/mta-audio-editor-packages`): contiene `mta-archive-key.asc`, gli indici `rpm/{channel}/{el9,el10}/repodata/` firmati e le pagine `packages/index.html` con i link ai binari sulle Releases.

Gli RPM non sono caricati sul repository Pages: la pagina `/rpm/early/el9/packages/` e l'equivalente `el10` presentano i link. DNF continua ad usare `baseurl=https://desalvo.github.io/mta-audio-editor-packages/rpm/early/el9` e scarica i pacchetti dalla Release grazie alla proprietà `xml:base` presente nel file `primary.xml`.

## Limiti di pubblicazione

- Nessun `.rpm` è ammesso nell'albero Pages.
- Nessun file Pages supera 45 MiB (soglia cautelativa inferiore all'avviso GitHub di 50 MiB).
- L'intero contenuto Pages non supera 900 MiB (inferiore al limite di pubblicazione di 1 GiB).
- Le versioni offerte dagli indici sono limitate dalle regole di retention già presenti nella pipeline (due per architettura); gli asset remoti delle versioni precedenti non vengono eliminati automaticamente.
- La pubblicazione dei nuovi indici avviene soltanto dopo la verifica dell'esistenza e della dimensione di ciascun asset caricato.
- Il passo finale verifica HTTP 200 per `repomd.xml`, la sua firma e la pagina di elenco su entrambi i target.

## Pubblicazione

Avvia manualmente **Publish signed server packages to GitHub Pages** dopo una esecuzione **Native server offline runtime matrix** superata sul medesimo commit di `main`. Usa il suo `run_id` come parametro `verified_run_id` e seleziona `early` o `stable`. È necessario che il token del workflow possa scrivere release asset nel repository principale, e che la chiave SSH dedicata consenta l'aggiornamento del repository Pages.

## Limiti operativi

Il caricamento reale, la firma e il test di installazione via DNF devono essere verificati sulla GitHub Action: i test locali del publisher utilizzano metadati sintetici, non RPM reali. Questa modifica **non** completa la pubblicazione HTTP dei pacchetti DEB/APT: i DEB continuano a essere conservati nell'artifact firmato, come prima.
