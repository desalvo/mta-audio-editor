# MTA Audio Editor — repository navigabili e installazione nativa

## Navigazione GitHub Pages

Il progetto `packaging/pages-repository/scripts/assemble_pages.py` genera automaticamente
una pagina `index.html` per ciascuna cartella del sito pubblicato. Mostra i file,
i link diretti e la dimensione. Nessuna modifica è apportata agli indici firmati APT/DNF.

Per attivare: copiare lo script aggiornato in
`desalvo/mta-audio-editor-packages/scripts/assemble_pages.py`, effettuare commit
nel repository `mta-audio-editor-packages` e rieseguire il workflow Pages.
Le pagine generate sono visibili sotto:
`https://desalvo.github.io/mta-audio-editor-packages/`

## Installazione server

Da questo cumulativo, l'installer nativo usa automaticamente:

- URL: `https://desalvo.github.io/mta-audio-editor-packages`
- Fingerprint chiave GPG: `0833A4FCB008ECAC9F98840B4C1D2DD95F5AEDB7`

Su una VM di test con la checkout aggiornata:

```
sudo bash scripts/install_mta.sh --native-server early --dry-run
sudo bash scripts/install_mta.sh --native-server early
```

Prima dell'installazione verifica che la distribuzione disponga delle dipendenze
(RHEL 10 non ancora qualificato per il pacchetto RPM attuale).
Il fingerprint è fissato nel programma ma viene comunque confrontato con la chiave
scaricata. Un override `MTA_REPO_KEY_FINGERPRINT` resta possibile solo se indicato
esplicitamente dall'amministratore, per repository/firme alternativi.

Rimane obbligatoria la validazione GPG del repository APT/DNF.
