# Secure development baseline

MTA Audio Editor adotta una baseline **defense in depth** ispirata alle pratiche OWASP e NIST Secure Software Development Framework. La mappatura descrive controlli implementati; non è una certificazione di conformità.

| Area | Controllo implementato |
|---|---|
| Access control | HTTP Basic default-on; nessuna password predefinita; manuale amministratore protetto. |
| Request integrity | Richieste che modificano dati richiedono `X-MTA-Request: 1`, riducendo il rischio CSRF con credenziali Basic memorizzate dal browser. |
| Path confinement | Project ID, filename audio e attachment validati e confinati nel project root. |
| Input handling | Limiti upload, limiti Pydantic, FFprobe di validazione, track-count enforcement. |
| Security headers | CSP, nosniff, frame deny, no-referrer, Permissions-Policy e cache-control API. |
| Injection | FFmpeg/FFprobe invocati con argument array e senza shell. |
| Supply chain | Versioni Python fissate, Dependabot, pip-audit, Trivy, SBOM e provenance BuildKit. |
| SAST / secret scanning | Bandit, CodeQL e Gitleaks. |
| Testing | pytest + branch coverage con gate minimo 70%; smoke test container. |
| Runtime isolation | UID/GID 10001, read-only root filesystem, capability drop, no privilege escalation, seccomp RuntimeDefault, service-account token disabilitato. |
| Secrets | Password solo da env/Secret; nessun secret reale incluso nel repository. |
| Error handling | Risposte controllate senza stack trace o output FFmpeg dettagliato verso il client. |

## Threat model sintetico

Gli asset principali sono file audio/MTA, progetti, credenziali amministrative e integrità degli export. Gli ingressi non fidati sono upload, parametri HTTP e modelli progetto inviati dal browser. I confini principali sono browser -> HTTP service, service -> FFmpeg e service -> filesystem/PVC.

Mitigazioni prioritarie: autenticazione, TLS esterno, request integrity, path confinement, media validation, limite dimensioni, no-shell subprocess, container hardening, dependency scanning e backup del PVC.

## Responsabilità del deployment

- terminare HTTPS su un Ingress/reverse proxy affidabile;
- utilizzare un secret manager invece del Secret di esempio in chiaro nel manifest;
- limitare l'esposizione di rete e, ove possibile, applicare NetworkPolicy;
- centralizzare log e allarmi;
- eseguire backup e test di restore del PVC;
- mantenere base image/dipendenze aggiornate;
- rieseguire periodicamente i gate di sicurezza;
- validare output MTA sul dispositivo Merish target prima dell'uso live.

## Vulnerability reporting

Seguire `SECURITY.md`. Non inserire credenziali, file MTA sensibili o exploit completi in issue pubbliche.

## Audio plugin and stem-separation security

- Audio insert processing uses a server-side allow-list of plugin types and named presets. The browser cannot submit arbitrary FFmpeg filter graphs.
- FFmpeg, FFprobe and Demucs are executed with argument arrays and never through a shell.
- Stem-separation model names are allow-listed before process execution.
- Uploaded media is size-limited and probed before processing.
- Demucs model weights are cached under the persistent application data directory; production operators should control outbound network access and may preload the cache in restricted environments.
