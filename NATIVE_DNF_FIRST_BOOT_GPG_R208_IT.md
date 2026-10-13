# Bootstrap DNF firmato su EL9/EL10 — r208

## Problema

Al primo avvio su una macchina vergine, l'importazione della chiave tramite `rpm --import` non inizializza necessariamente la cache delle chiavi di verifica dei metadati DNF (`repo_gpgcheck=1`). I probe brevi sulle dipendenze possono quindi scadere prima che la chiave venga accettata manualmente.

## Correzione

Subito dopo avere scritto la configurazione del repository firmato, l'installer esegue `dnf -y --refresh --disablerepo='*' --enablerepo=mta-audio-editor makecache`, con timeout totale di 180 secondi e timeout/retry di rete delimitati. Questa fase accetta automaticamente solo la chiave del repository MTA la cui impronta digitale è già stata confrontata con quella attesa; le verifiche `gpgcheck=1` e `repo_gpgcheck=1` rimangono obbligatorie.

L'operazione non modifica lo stato di EPEL né gli altri repository, non installa pacchetti e non tocca i dati MTA. Un problema di rete o una firma non valida provoca un arresto esplicito prima dell'installazione.

## Test

Test statici locali della sequenza, dei controlli GPG e del bootstrap; il collaudo reale DNF su macchina vergine EL10 deve ancora essere eseguito.
