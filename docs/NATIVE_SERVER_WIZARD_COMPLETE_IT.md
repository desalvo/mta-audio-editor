# Wizard nativo RPM/DEB (0.3.0-r208)

`sudo bash install_mta.sh` installa, tramite repository firmati, il server nativo e avvia la configurazione interattiva. La distribuzione da sorgenti richiede `--legacy-source`.

* `sudo bash install_mta.sh early --unattended`: installazione non interattiva con configurazione predefinita, senza aprire porte firewall.
* `sudo bash install_mta.sh --configure-only`: riesegue il wizard senza reinstallare il pacchetto.
* `sudo bash install_mta.sh --no-wizard`: installazione del solo pacchetto e configurazione minima.
* `sudo bash install_mta.sh --dry-run`: simula il bootstrap.

Il wizard permette porta, bind, account e password admin, directory dati, dispositivo AI, URL pubblico, TLS esistente oppure certificato self-signed (validità 365 giorni con SAN), ACE-Step locale o remoto via HTTPS (token opzionale) e timer billing. Può aprire la porta del server tramite firewalld o UFW **soltanto** quando il servizio firewall è già attivo e l'utente richiede esplicitamente l'apertura. `--unattended` non cambia il firewall. Non modifica o disabilita le firme GPG né installa pacchetti da URL RPM/DEB arbitrari. Il wizard installa tramite repository configurati `openssl` se necessario a generare TLS; il gestore pacchetti risolve le dipendenze obbligatorie.

La modifica delle impostazioni è atomica per `/etc/mta/mta.env` e in caso di errore al riavvio ripristina il file precedente. La rotazione password e dei token è esplicita; la configurazione conserva gli altri segreti. I certificati autogenerati non sostituiscono automaticamente un certificato esistente e **non** sono certificati attendibili pubblicamente. Per esposizione Internet usare certificati emessi da una CA fidata e configurare proxy e DNS secondo il proprio ambiente. L'apertura di una porta locale non configura NAT, security group, reverse proxy o DNS.

**Limiti operativi:** il wizard ACE-Step configura il collegamento al servizio remoto ma non installa né amministra il backend remoto; altri adapter AI usano configurazioni e credenziali dedicate. Il server richiede controlli end-to-end, SELinux e certificazione su VM EL10 prima della produzione.
