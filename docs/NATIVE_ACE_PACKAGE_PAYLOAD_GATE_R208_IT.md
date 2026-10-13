# MTA Audio Editor 0.3.0-r208 — ACE-Step installer nel pacchetto nativo

Il wizard può offrire ACE-Step locale solo se il pacchetto RPM/DEB installato contiene `/usr/lib/mta-audio-editor-server/native-installers/install_ace_step.sh` eseguibile. Il relativo installer ROCm deve essere incluso nello stesso pacchetto.

La build esegue `scripts/server_packages/verify_native_installers.py` sul file RPM/DEB **effettivo**, verificando la presenza dei due helper e i relativi permessi di esecuzione. La CI esegue inoltre controlli sul payload di EL9, EL10 e DEB e fixture positive/negative.

## Verifica sul sistema EL10 già installato

```bash
rpm -q mta-audio-editor-server
rpm -ql mta-audio-editor-server | grep '/native-installers/'
rpm -V mta-audio-editor-server
ls -l /usr/lib/mta-audio-editor-server/native-installers/
sudo dnf --refresh upgrade mta-audio-editor-server
sudo bash /usr/lib/mta-audio-editor-server/native-installers/install_ace_step.sh --dry-run --device cpu
```

La riga finale richiede il pacchetto aggiornato; non eseguire quella riga prima di aver verificato la presenza del file. Per la riconfigurazione, riavviare `install_mta.sh --configure-only` dopo l'upgrade. L'aggiornamento deve provenire dal repository firmato già configurato, senza scaricare helper arbitrari.

**Attenzione**: un pacchetto ancora identificato come `0.3.0-0.208.early.el10` potrebbe contenere il vecchio payload anche dopo la correzione dei sorgenti; è necessario ricostruire e pubblicare il pacchetto corretto, conservando revisione logica r208 e verificando che DNF riconosca un aggiornamento installabile (release RPM distinta/epoch coerente, senza modificare il numero di revisione dell'applicazione).

I test locali sul payload non sostituiscono test di installazione ACE-Step con download modelli, accesso alla rete, installazione ROCm né convalida GPU sul sistema EL10. La presenza del servizio e il suo avvio vanno verificati sul sistema reale con `systemctl is-enabled mta-ace-step.service`, `systemctl is-active mta-ace-step.service`, `journalctl -u mta-ace-step.service -n 100 --no-pager` e una chiamata di inferenza end-to-end.
