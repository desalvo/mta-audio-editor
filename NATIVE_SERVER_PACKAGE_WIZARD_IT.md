# MTA Audio Editor 0.3.0-r208 — wizard per installazione nativa

L'installazione predefinita di `scripts/install_mta.sh` usa esclusivamente i pacchetti firmati APT/DNF. Il canale predefinito per la serie in early release è `early`.

* `sudo bash install_mta.sh` — installa da repository e apre il wizard interattivo.
* `sudo bash install_mta.sh --native-server early` — stesso comportamento esplicito.
* `sudo bash install_mta.sh --native-server early --unattended` — configura con valori sicuri conservando credenziali già presenti; non attende input.
* `sudo bash install_mta.sh --native-server early --no-wizard` — installa pacchetto e conserva configurazione minima.
* `sudo bash install_mta.sh --native-server early --configure-only` — riconfigura senza reinstallare il pacchetto.
* `sudo bash install_mta.sh --legacy-source` — precedente installazione da sorgenti, solo su richiesta esplicita.

Il bootstrap scarica il wizard e gli altri due helper, tutti dallo stesso SHA GitHub. Richiede curl e Python 3 per la risoluzione del commit.

Il wizard di questa versione permette di impostare porta, host (locale/rete), username amministratore, password opzionale, directory progetti, percorso certificati TLS esistenti, preferenza dispositivo AI, URL pubblico e abilitazione del timer billing. Le modifiche conservano le credenziali e i valori non modificati in `/etc/mta/mta.env` e riavviano soltanto il server nativo. Se la configurazione non esiste o il pacchetto non è installato, il wizard si rifiuta di procedere.

**Pacchetti:** le dipendenze obbligatorie sono installate direttamente da APT/DNF. Le eventuali utility opzionali sono prelevate soltanto dai repository configurati, dopo consenso nell'uso interattivo. Non sono eseguiti download diretti di RPM/DEB né disattivati controlli GPG. In modalità unattended non viene installato software opzionale non necessario alla configurazione scelta; ogni dipendenza obbligatoria è invece risolta automaticamente da APT/DNF.

**Attenzione:** questo wizard non include ancora la generazione di certificati self-signed, una procedura di apertura firewall o una configurazione applicativa completa dei backend AI remoti. Utilizzare certificati TLS già presenti e le impostazioni nell'app per le configurazioni avanzate.

Il codice non è stato validato con una vera transazione di installazione su VM EL10 dopo queste modifiche: eseguire il test di integrazione prima di distribuirlo in produzione.
