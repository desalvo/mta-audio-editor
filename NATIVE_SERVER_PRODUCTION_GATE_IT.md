# MTA Audio Editor 0.3.0-r208 — Gate produzione server nativo

**Esito: NON CERTIFICATO per la produzione.** Nessun commit/push o intervento sul CT 130 effettuato.

## Verificato localmente
- Builder DEB e RPM: controlli statici, interpretazione dei requisiti release-ready, prove offline e sintassi.
- 23 test locali mirati superati, workflow GitHub Actions parseabili.
- RPM controlla la prova della wheelhouse con il Python 3.12 usato per costruirla.
- DEB vincola la versione minor di Python nel campo `Depends` quando generato in modalità release-ready.
- Runtime Python promosso controllato anche dopo il rename; backup rimosso solo dopo esito positivo.

## Blocchi di produzione
- La nuova matrice CI deve essere eseguita e terminare con successo sul commit esatto.
- Test DNF install/reinstall **reale** ancora assente dalla matrice Rocky; è presente soltanto il controllo dello script.
- Ubuntu 24.04 richiede una pipeline di build/installazione Python 3.12 distinta dalla DEB Debian 13 Python 3.13.
- Mancano test end-to-end dei servizi, credenziali, upgrade/downgrade, recovery e persistenza con package manager.
- Mancano chiavi GPG e identità di firma verificate, repository effettivamente pubblicato e client indipendenti per convalida firme.
- Migrazione sicura wizard/Git, rollback applicativo e test dei codec su Rocky non ultimati.

**NON usare il pacchetto di test sul CT 130. Non attivare la pubblicazione automatica.**
