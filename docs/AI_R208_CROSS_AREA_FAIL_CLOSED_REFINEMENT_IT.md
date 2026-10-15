# MTA Audio Editor r208 — verifica trasversale AI e quarantena

## Correzione
La quarantena stem valida ora l'intero registro persistente prima di spostare un file. Un registro corrotto non può quindi provocare uno spostamento privo di tracciabilità. Una ricevuta già marcata in quarantena viene inoltre rifiutata prima dell'operazione. La scrittura atomica del registro e il rollback già presenti restano invariati.

## Verifiche
Batteria integrata: 106 test superati (8 warning), relativi a stem, billing remoto, e gestione native dei job AI pendenti. È incluso il nuovo test fail-closed sul registro corrotto. Non è una certificazione della regressione globale né dei collaudi hardware, del ciclo GPU effettivo o dei sistemi Windows/macOS reali.

## Vincoli
VERSION 0.3.0 / REVISION 208 invariati; nessun commit, push, tag o release.
