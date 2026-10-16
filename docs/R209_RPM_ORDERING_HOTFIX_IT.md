# r209 - Hotfix ordinamento release RPM

Il vecchio RPM Rocky Linux `0.209.1.early.el10` viene valutato più recente da rpm/dnf rispetto alla nuova release con suffix `0.209.1.early.b...el10`, perché il segmento `el10` precede `b...` nel confronto. Di conseguenza `dnf upgrade --refresh` segnala `Nothing to do`.

La CI del pacchetto nativo EL9/EL10 e il workflow di pubblicazione usano ora `0.<REVISION>.2.early.b<BUILD_INFO>.r<RUN_ID>.a<ATTEMPT>` (con `.el9` / `.el10` aggiunto da `%{?dist}`). Questo garantisce l'upgrade dai vecchi `0.<REVISION>.1.early.el*` senza cambiare VERSION e REVISION applicativi. I controlli publisher sui pacchetti della Matrix sono stati aggiornati allo stesso schema.

Effettuare commit e nuova Matrix; il Publish deve usare il Run ID della nuova Matrix sul medesimo commit. Verificare poi con `dnf --refresh list --showduplicates mta-audio-editor-server` e `dnf upgrade --refresh mta-audio-editor-server`.
