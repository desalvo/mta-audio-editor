# Collegamento ACE-Step al worker del server nativo — r208

Il servizio `mta-ace-step.service` attivo non abilita automaticamente il worker AI usato dalle API Arranger.
Il wizard configura ora `MTA_AI_WORKER_ENABLED=true` e il percorso assoluto verificato
`/usr/lib/mta-audio-editor-server/app/ace_step_http_worker.py` nei modi local/remote;
la modalità disabled disabilita il worker. Il catalogo mostra il modello disponibile
solo se il worker è effettivamente configurato ed eseguibile. Ciò **non** certifica
che la generazione del modello sia riuscita: occorre un test audio end-to-end.

Diagnostica dopo l'aggiornamento:

```bash
sudo systemctl restart mta-server.service
sudo systemctl status mta-ace-step.service mta-server.service --no-pager
sudo journalctl -u mta-server.service -n 80 --no-pager
```

Per installazioni già funzionanti, rieseguire `install_mta.sh --configure-only`
con ACE-Step local; il wizard conserverà le risposte nel checkpoint.
