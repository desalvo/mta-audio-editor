# MTA r210 — pubblicare i bundle Git / Publish Git bundles

Aggiornato / Updated: 11 novembre / November 2026.

## IT — Procedura dal proprio computer

Il file `MTA-r210-device-validation.bundle` contiene tutti e quattro i commit
locali successivi alla base `6dae37ec8128e07aeb59e20798c7e68ea7193daa`, inclusi
BS RoFormer, annullamento/revoca, evidenze diritti e verifica del dispositivo.
È sufficiente questo bundle; non serve importare anche quelli precedenti.
Importarlo conserva gli SHA originali. Il bundle è incrementale: prima occorre
un clone del repository che contenga la base. Lo ZIP cumulativo è invece una
copia completa dei sorgenti, inclusi gli allegati storici, senza `.git`.

Scaricare il bundle e il suo `.bundle.sha256` nella stessa cartella. Verificarlo
con `sha256sum -c MTA-r210-device-validation.bundle.sha256` da quella cartella;
su macOS usare `shasum -a 256 -c MTA-r210-device-validation.bundle.sha256`.
Poi eseguire da Bash, Git Bash o un terminale Linux/macOS con Git autenticato
per `desalvo/mta-audio-editor`:

```bash
(
  set -e
  BUNDLE="$HOME/Downloads/MTA-r210-device-validation.bundle"
  git clone https://github.com/desalvo/mta-audio-editor.git mta-bundle-publish
  cd mta-bundle-publish
  git bundle verify "$BUNDLE"
  git fetch "$BUNDLE" refs/heads/main
  git merge --ff-only FETCH_HEAD
  git log -4 --oneline
  git push origin HEAD:main
)
```

Adattare soltanto il percorso `BUNDLE`. La directory `mta-bundle-publish` deve
essere nuova. Il blocco si ferma al primo errore. Se manca l'autenticazione,
configurarla sul proprio computer; con GitHub CLI sono disponibili
`gh auth login` e `gh auth setup-git`. Non incollare token nella chat.

Se `--ff-only` o il push vengono rifiutati perché `main` è avanzato in modo
divergente, fermarsi e riconciliare le modifiche sul nuovo stato remoto.
Non usare `--force`, reset distruttivi o riscritture degli SHA per risolvere
quel rifiuto. Eventuali protezioni del repository restano applicabili.

## IT — Verificare la pubblicazione e la full CI

Dal clone appena usato confrontare `git rev-parse HEAD` con
`git ls-remote origin refs/heads/main`. Subito dopo il push devono indicare
lo stesso commit, salvo successivi aggiornamenti di altri autori.

Il commit finale contiene `[full-ci]`: nel workflow corrente
`.github/workflows/ci-cd.yml` il push su `main` seleziona la validazione
completa di **CI / Production image**. Aprire
[Actions](https://github.com/desalvo/mta-audio-editor/actions) e controllare il
run dello stesso SHA. Un push riuscito non certifica che la CI sia verde.

Solo se serve avviare una nuova esecuzione manuale, usare Actions →
**CI / Production image** → **Run workflow**, branch `main`,
`full_validation=true`; oppure, dal clone con GitHub CLI autenticata:

```bash
gh workflow run ci-cd.yml --ref main -f full_validation=true
gh run list --workflow ci-cd.yml --branch main --limit 5
```

Evitare un secondo avvio mentre il primo run è in corso: il workflow ha
`cancel-in-progress: true`. Dopo la verifica comunicare lo SHA pubblicato e
l'URL del run per aggiornare handoff e stato. L'importazione dei commit non
abilita la policy del modello e non conclude la revisione dei diritti.

## EN — Publish from your own computer

Download `MTA-r210-device-validation.bundle` and its `.bundle.sha256`.
This latest bundle contains all four unpublished commits after base
`6dae37ec8128e07aeb59e20798c7e68ea7193daa`; older bundles are unnecessary.
It preserves the original commit SHAs and requires an existing clone containing
that base. The cumulative ZIP contains complete source and historical
attachments, without Git history.

Verify the checksum using `sha256sum -c` (macOS: `shasum -a 256 -c`), then run
the Bash block above on a computer authenticated for this repository. Adjust
the download path and use a new `mta-bundle-publish` directory. The block stops
on errors. If remote history has diverged, stop and reconcile it; do not force
push or rewrite history. Repository protections still apply.

Compare `git rev-parse HEAD` with `git ls-remote origin refs/heads/main` after
publishing. The final commit's `[full-ci]` marker selects the full validation
in **CI / Production image**. Verify the Actions run for that exact SHA.
If a fresh manual run is needed, select `main` and `full_validation=true`,
or use the GitHub CLI commands above. Avoid duplicate runs while one is active
because the concurrency policy cancels an earlier run.

Publishing source does not enable the model policy or certify checkpoint
rights, neural inference or musical quality. Record the actual SHA and CI URL
in the current handoff after publishing.

## Riferimenti / References

- [Git bundle](https://git-scm.com/docs/git-bundle)
- [Git merge, --ff-only](https://git-scm.com/docs/git-merge)
- [Manual GitHub Actions runs](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow)
