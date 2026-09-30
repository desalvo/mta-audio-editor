# MTA Audio Editor 0.2.0-2

![MTA Audio Editor](app/static/logo.svg)

![MTA Audio Editor DAW](app/static/mockup-reference.png)

Web DAW containerizzata per creare, importare, modificare ed esportare progetti multitraccia MTA destinati a M-Live/Merish ed equivalenti.

**Creatore:** Alessandro De Salvo <braket71@gmail.com>  
**Repository:** `desalvo/mta-audio-editor`  
**Licenza:** EUPL-1.2  
**Versione:** `0.2.0-2`  
**Build:** generato automaticamente nel formato `YYYYMMDD-HH:MM:SS`.

## Funzioni principali

- timeline grafica multitraccia in stile DAW con waveform e zoom;
- selezione e rimozione di segmenti su una o più tracce;
- taglio globale del brano con riallineamento di tutte le tracce e degli eventi temporali;
- ripple editing opzionale sulle tracce selezionate;
- editing non distruttivo basato su clip/regioni;
- import di nuove tracce e sostituzione di tracce esistenti;
- sincronizzazione manuale in millisecondi e automatica tramite correlazione dell'inviluppo audio;
- interfaccia completamente ridisegnata in stile DAW professionale, fedele al mockup incluso in `app/static/mockup-reference.png`;
- mixer con fader, pan, mute, solo, meter e master bus;
- import diretto di MP3/WAV e sostituzione di singole tracce;
- separazione MP3 in stems indipendenti tramite plugin Demucs, da aggiungere a un MTA esistente o nuovo;
- catene insert per traccia e master, fino a 16 effetti: EQ, normalizer, compressor e limiter con preset allow-listed;
- preview master renderizzata applicando timeline, insert, mixer e processing master;
- export MTA8/MTA16, WAV PCM 24-bit/44.1 kHz e MP3 320 kbps;
- gestione testo, accordi e marker temporali;
- preservazione degli attachment MTA esistenti quando estraibili;
- documentazione utente e amministratore integrata e scaricabile in PDF.

## Avvio Docker

```bash
export MTA_ADMIN_PASSWORD='una-password-lunga-e-casuale'
docker compose up -d --build
```

La build production include per default il plugin Demucs. Per un’immagine core più piccola senza stem separation: `docker build --build-arg INSTALL_STEMS=false .`.

Aprire `http://localhost:8080`. L'autenticazione è abilitata per default; l'utente predefinito è `admin`, ma **non esiste una password predefinita**.

## Kubernetes

Creare il Secret applicativo fuori dal repository e poi applicare il manifest:

```bash
kubectl create secret generic mta-audio-editor-auth \
  --from-literal=username=admin \
  --from-literal=password='una-password-lunga-e-casuale'
kubectl apply -f k8s/deployment.yaml
kubectl port-forward svc/mta-audio-editor 8080:80
```

In produzione usare un Ingress/reverse proxy HTTPS e un gestore di secret appropriato.

## Documentazione

- `/docs/user` - manuale utente online, pubblico;
- `/docs/pdf/user` - manuale utente PDF;
- `/docs/admin` - manuale amministratore, protetto da autenticazione;
- `/docs/pdf/admin` - manuale amministratore PDF, protetto da autenticazione;
- `docs/SECURE_DEVELOPMENT.md` - baseline di sviluppo sicuro.

## CI/CD GitHub

La pipeline `.github/workflows/ci-cd.yml` applica i gate prima di pubblicare immagini:

1. compile + Ruff;
2. unit/integration test e coverage minima 70%;
3. Bandit SAST;
4. `pip-audit` sulle dipendenze Python;
5. Gitleaks;
6. Trivy filesystem scan;
7. build immagine locale;
8. Trivy image scan;
9. smoke test autenticato e verifica delle route pubbliche/protette.

Solo dopo il superamento dei gate:

- push su `main` -> `desalvo/mta-audio-editor:latest`;
- push di un tag -> `desalvo/mta-audio-editor:<tag>`.

Le immagini sono pubblicate per `linux/amd64` e `linux/arm64`, con provenance e SBOM BuildKit.

### Secret GitHub richiesti

Definire come **Repository secrets**:

- `DOCKERHUB_USERNAME`
- `DOCKERHUB_TOKEN`

## Primo push e release

```bash
git init
git branch -M main
git remote add origin https://github.com/desalvo/mta-audio-editor.git
git add .
git commit -m "Initial production release 0.2.0-2"
git push -u origin main
```

Dopo che la CI su `main` è verde, creare il tag:

```bash
git tag -s 0.2.0-2 -m "MTA Audio Editor 0.2.0-2"
git push origin 0.2.0-2
```

## Packaging locale

`./scripts/package.sh` aggiorna automaticamente `BUILD`, rigenera i PDF, esegue i production gate, rimuove cache/artefatti temporanei e genera lo ZIP versionato.

## Sicurezza e produzione

L'applicazione applica autenticazione default-on, request-integrity header sulle operazioni mutative, confinamento dei path, limiti upload, validation dei media, security header, container non-root/read-only e gate di sicurezza CI. Questo costituisce una baseline production-oriented, non una certificazione formale. TLS, secret management, backup, monitoring, network policy e validazione su hardware Merish restano responsabilità del deployment.

## Compatibilità MTA

Il layer MTA è isolato in `app/codec.py`. Gli attachment non audio già presenti vengono preservati quando tecnicamente estraibili e l'editor aggiunge `mta-editor.json` con il modello non distruttivo. Metadati proprietari Merish non documentati devono essere validati su file campione reali prima di dichiarare compatibilità bit-perfect.
