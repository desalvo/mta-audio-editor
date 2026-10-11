# Optional HTTPS for the MTA web server / HTTPS opzionale per il server web MTA

## English

The Linux `scripts/install_mta.sh` wizard continues to use HTTP by default. To enable HTTPS, run the wizard and answer **yes** to `Enable HTTPS for the MTA web interface`; select **existing** (provide the absolute paths to a PEM certificate and matching private key) or **self-signed** (provide the DNS hostname or IP used by clients). For noninteractive setup:

```bash
sudo bash scripts/install_mta.sh --yes --https yes --tls-mode self-signed --tls-name mta.example.org --port 8443
sudo bash scripts/install_mta.sh --yes --https yes --tls-mode existing --tls-cert /etc/ssl/certs/mta.pem --tls-key /etc/ssl/private/mta.key --port 8443
```

HTTPS replaces HTTP on the selected port; it is not a second exposed HTTP listener. The certificate and key are checked for validity and matching public keys. Self-signed certificates are generated with a Subject Alternative Name and stored at `/etc/mta/tls/server.crt` and `/etc/mta/tls/server.key`; existing generated certificates are reused until an administrator replaces or removes them. The private key is restricted to mode 0600. The installer remembers TLS settings in the root-owned `/etc/mta/mta-wizard.conf` and configures Uvicorn through `/etc/mta/mta.env`. Switch back using `--https no`. A self-signed certificate must be explicitly trusted by clients; prefer a CA-issued certificate for public deployments. The installer health check intentionally uses `curl --insecure` only for the local loopback probe, not client traffic.

## Italiano

Il wizard Linux `scripts/install_mta.sh` mantiene **HTTP come impostazione predefinita**. Per abilitare HTTPS, rispondere **yes** alla domanda `Enable HTTPS for the MTA web interface` e scegliere **existing** (percorsi assoluti del certificato PEM e della chiave privata corrispondente) oppure **self-signed** (nome DNS o indirizzo IP utilizzato dai client). Per l'installazione non interattiva usare gli esempi sopra.

HTTPS sostituisce HTTP sulla porta selezionata: non viene aperta una seconda porta HTTP. Certificato e chiave vengono verificati e, in modalità self-signed, generati con SAN e salvati in `/etc/mta/tls` (chiave con permessi 0600). La configurazione viene conservata per successive reinstallazioni; `--https no` ripristina HTTP. I certificati self-signed devono essere considerati attendibili esplicitamente dai client; per ambienti pubblici è consigliato un certificato emesso da una CA. Il controllo `curl --insecure` è limitato al probe locale dell'installer.
