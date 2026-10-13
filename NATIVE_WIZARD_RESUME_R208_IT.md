# MTA 0.3.0-r208 — Ripresa del wizard nativo

Il wizard memorizza progressivamente ogni scelta valida in
`/etc/mta/.mta-wizard.pending`, con permessi `0600` e proprietario root.
La configurazione in uso (`/etc/mta/mta.env`) rimane invariata fino al commit
finale. Un errore o una interruzione conserva le risposte per la successiva
esecuzione `sudo bash install_mta.sh --configure-only`.

**Sicurezza:** il checkpoint può contenere password e token; non copiarlo nei
log, nei ticket di assistenza o nei backup non cifrati. Per ricominciare da
zero, solo dopo averne valutato le implicazioni, eseguire
`sudo rm -f /etc/mta/.mta-wizard.pending`.

Il checkpoint viene eliminato soltanto dopo completamento della configurazione.
La modalità non interattiva eredita i valori salvati, ove presenti. Sono necessari
collaudi reali su EL10 per provare riavvio, rollback, ACE-Step e ROCm.
