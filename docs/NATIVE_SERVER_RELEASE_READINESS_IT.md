# MTA Audio Editor 0.3.0-r208 — verifica di produzione server

## Nuovi gate predisposti (da convalidare su GitHub Actions)

- Ubuntu 24.04 con Python 3.12: wheelhouse per ABI locale, build, installazione e reinstallazione DEB.
- Rocky Linux 9: repository EPEL per ffmpeg-free, build RPM e installazione/reinstallazione reale con DNF in container usa-e-getta; import dell'applicazione e persistenza di progetti/configurazione.
- Repository APT: test end-to-end con chiave GPG effimera, indice verificato da APT e installazione effettiva di un pacchetto fixture, isolato da ogni chiave produttiva.
- Test locali mirati: 28 superati (inclusi due scenari simulati di promozione e rollback della virtualenv).

## Condizioni ancora necessarie prima dell'uso su sistemi di produzione

1. Nuovi job GitHub Actions tutti verdi **sullo stesso commit**, inclusi DNF reale e Ubuntu 24.04.
2. Test avvio `mta-server.service` e `mta-billing-scheduler.service` con systemd in ambiente isolato e health check HTTP autenticato.
3. Failure injection su upgrade e rollback del package manager, incluse interruzioni e verifiche di persistenza di configurazioni e progetti.
4. Firma RPM, metadata DNF firmati, firma APT e prova di installazione da entrambi i repository reali, dopo gestione sicura delle chiavi GPG.
5. Migrazione del vecchio wizard esplicita, verificata e reversibile prima del passaggio del CT 130.

Le build e i job di validazione non costituiscono da soli una certificazione. **Nessuna pubblicazione né modifica al CT 130.**

## Ulteriori correzioni pre-commit

- Ubuntu 24.04: la preparazione della wheelhouse usa `/opt/mta-ci-python` (virtualenv temporanea), evitando PEP 668 sul Python di sistema; il builder valida il proof con lo stesso Python 3.12.
- Repo APT fixture: directory temporanee attraversabili dall’utente `_apt` e verifica `apt-get install` da indice firmato (solo container CI).
- Virtualenv: prove simulate che verificano sia il ripristino del runtime precedente in caso di fallimento dopo promozione, sia la pulizia dopo promozione riuscita.

**Avvertenza:** il test di firma usa una chiave temporanea non adatta alla distribuzione. Non sono state eseguite prove systemd reali, firma RPM di produzione, downgrade del package manager o migrazione live.

## Ulteriore preparazione precommit: systemd e HTTP

- `mta-server.service` dichiara `Delegate=cpu io` per il launcher cgroup v2; le unità sono sottoposte a `systemd-analyze verify` sulla matrice Ubuntu (il runner privo della venv installata può mostrare un'avvertenza sul percorso ExecStart).
- `mta-billing-scheduler.service` diventa `Type=oneshot` ed è richiamato da `mta-billing-scheduler.timer` ogni ora, con `Persistent=true`. DEB e RPM contengono la unit timer e attivano servizio web e timer nel post-install (best effort nei container senza systemd).
- I test CI di installazione/reinstallazione DEB e RPM aggiungono il controllo HTTP reale dell'applicazione (`/api/health`) tramite `http_smoke.py`, con dati e porta temporanei nel container usa-e-getta. Il test non equivale a un avvio tramite PID 1/systemd.
- Nuovi test strutturali verificano unit, timer, loro inclusione nei due formati e smoke HTTP; **33 test locali di packaging superati**.

## Precisazioni fondamentali

Questi interventi sono pre-commit. **Non esiste ancora una certificazione finale:** non è stata eseguita la nuova matrice remota né un test di avvio unit sotto PID 1/systemd, rollback del package manager su due versioni reali, né una prova con chiavi/repository di produzione. La migrazione reversibile da wizard legacy rimane bloccata intenzionalmente; il CT 130 non è stato modificato. Non installare questi pacchetti sui sistemi in esercizio finché tali gate non sono superati.

## Gate systemd VM e autenticità repository (ulteriore ciclo pre-commit)

- Introdotto `scripts/server_packages/check_system_services.sh`, che **rifiuta** l'esecuzione fuori da una VM usa-e-getta autorizzata (`MTA_CI_DISPOSABLE_VM=1`, root e systemd come PID 1). Verifica unit, delega cgroup, server, timer billing, esecuzione del job oneshot e health HTTP su localhost:8000.
- Aggiunto il job `ubuntu-systemd-vm` nel workflow `server-native-runtime-validation.yml`: crea pacchetto nativo con wheelhouse offline, installa su runner Ubuntu 24.04 temporaneo, testa le unit sotto systemd reale, reinstalla il DEB e controlla configurazione e stato persistente.
- Rafforzata la verifica del repository APT firmato: un file `Release` manomesso deve essere respinto dalla verifica GPG; rimangono le prove precedenti di installazione da indice firmato con chiave effimera.
- 38 test locali mirati superati, shell e YAML convalidati. **Il job VM non è stato ancora eseguito su GitHub Actions.**

### Blocchi non aggirabili con soli test locali

1. Eseguire realmente su GitHub Actions la nuova matrice, inclusi Ubuntu VM/systemd, Ubuntu container, Rocky DNF e firma APT effimera.
2. Eseguire un downgrade di package manager tra *due release differenti* e testare rollback di aggiornamento interrotto; la reinstallazione della stessa versione e il rollback della virtualenv non lo sostituiscono.
3. Firmare i pacchetti RPM e gli indici RPM/DNF con chiavi detenute e protette dal publisher; quindi installare da repository firmato con verifica GPG abilitata. La firma temporanea CI non è una firma di produzione.
4. Validare migrazione legacy reversibile e backup su ambiente copia del CT 130, non sul sistema produttivo.

La preparazione pre-commit non equivale alla certificazione finale. Nessun push, firma produttiva o mutazione di CT 130.
