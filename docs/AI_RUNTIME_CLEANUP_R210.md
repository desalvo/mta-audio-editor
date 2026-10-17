# Pulizia automatica ambienti AI — 0.3.0-r210

Le directory `/opt/mta/ai-<16 caratteri esadecimali>` contengono runtime Python, non cache eliminabili indiscriminatamente. Il wizard RPM/DEB attiva la pulizia solo dopo setup, riavvio del servizio e completamento delle fasi finali riusciti. Il percorso legacy la esegue dopo la verifica HTTP del servizio.

La pulizia conserva gli ambienti citati nel file di configurazione corrente o in `/etc/mta/mta.env`. In presenza di `/etc/mta/.mta-wizard.pending` rinvia tutte le rimozioni, preservando il setup riprendibile. Conserva directory più recenti di 24 ore. Non è un timer: gli ambienti recenti saranno rivalutati al prossimo setup riuscito o alla successiva esecuzione manuale.

Prima di eliminare controlla i riferimenti in `/proc`: command line, ambiente, mappe di memoria, eseguibile, directory corrente e file descriptor. Una scansione non consentita rinvia la pulizia. Non termina processi e non cambia la configurazione di runtime o billing.

Non elimina directory con nome diverso dal pattern previsto, symlink, directory non appartenenti all'utente che esegue setup, directory scrivibili da gruppo/altri, filesystem montati o bind mount interni. I symlink interni non vengono seguiti. Usa la rimozione Python protetta da attacchi tramite symlink. Un lock comune serializza setup e pulizia avviati dal nuovo installer. Errori di pulizia non invalidano un setup già riuscito; sono riportati come `deferred`.

## Anteprima senza eliminazioni

Dopo l'aggiornamento dell'RPM:

```bash
sudo /opt/mta/server-venv/bin/python /usr/lib/mta-audio-editor-server/native-installers/install_ai_engines.py --cleanup --dry-run
```

Il campo `removed` elenca in questo caso i candidati, senza cancellarli. Per eseguire la pulizia manualmente togliere `--dry-run`. `--base` e `--env-file` consentono percorsi personalizzati; i default sono `/opt/mta` e `/etc/mta/mta.env`.

Le directory dei modelli, i progetti, ACE e gli altri venv non appartenenti al pattern non sono oggetto della pulizia. Le directory recenti o non verificabili rimangono sul disco intenzionalmente. Non sono state eseguite pulizie su server reali durante lo sviluppo.

## Verifica

Test in directory temporanee: eliminazione ambiente obsoleto, protezione ambiente configurato e recente, anteprima, checkpoint, processi e file aperti, errori di accesso a proc, bind mount, symlink e permessi non sicuri. Verificato l'ordine di invocazione dei due wizard. La prova completa su EL10 rimane da eseguire.
