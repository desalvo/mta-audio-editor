# Validazione media/stems/cleanup — 0.3.0-r210

2026-10-17 UTC. Versione invariata. Base cumulativa completa:
MTA-r210-native-ai-accounts.zip, 1491 file,
SHA-256 ea92fb28ca74c6ba6840eabbcda5b91cf29c78dca82b93acbbc08f820cd15f2d.
Tutti gli sviluppi precedenti non ancora committati sono conservati.
Nessun commit, push, tag, release, invio email reale o modifica del server effettuati.

## Esiti finali

- **3414 passed, 4 skipped, 10 deselected**, zero failure/error, 194,04 secondi.
- Copertura applicazione **75.08%**, soglia 70% superata; XML incluso.
- Gruppo mirato finale: **60 passed**, JUnit e log inclusi.
- Ruff app/native/tests/install_demucs.py/k8s-wizard.py: superato.
- Node --check app.js e bash -n build_deb.sh/build_rpm.sh: superati.
- CRC dell'archivio finale e confronto byte per byte con i file di lavoro.
- Conservati tutti i 1491 file della base; 11 file esistenti aggiornati,
  aggiunte esplicite elencate nel manifest changes.txt. Permessi preservati.

I 4 skip riguardano SDK Steinberg/ADelay opzionali assenti. I 10 test AF_UNIX
sono esclusi con la stessa selezione esplicita dei cicli precedenti: non sono
dichiarati superati. Warning e motivazioni rimangono nel log finale.

## Copertura delle correzioni

Import YouTube con trasporto yt-dlp simulato, WAV reale e pipeline di pubblicazione
del progetto: successo, riapertura, journal eliminato e originale mantenuto.
Errore di conversione: rimozione dei soli file posseduti dall'import fallito,
conservazione dell'originale estraneo e niente media/journal residui.

Clip di libreria senza tracce mostrate come riutilizzabili e cancellabili, non
come in uso. Eliminazione HTTP rimuove in modo durabile la voce di libreria prima
del file. Cleanup conserva timeline, originali e sorgenti accodate, rimuove media
orfani e clip inutilizzate, elimina solo temporanei riconosciuti e obsoleti.
Protezione degli upload in corso, rifiuto di journal malformati, rilascio delle
riserve al termine dei job, ACL fra utenti, integrità delle richieste e policy
esplicita di pulizia. Un alias symlink non può cancellare un altro file usato.

Separazione traccia via HTTP web e native remota: ammissione alla coda persistente,
pubblicazione di stems WAV di prova, riapertura e file presenti. Recupero di sorgente
promossa al deposito condiviso: accettati solo hardlink del blob con contenuto
e identità verificati; link arbitrari e contenuto modificato vengono respinti.

Esecuzione di un vero processo di prova per il Python Demucs esterno, comando
senza shell e selezione dispositivo inoltrata. Adattatore remoto e profiler
riutilizzano lo stesso interprete. Installer con Torch/Torchaudio ROCm vincolati
e tutte le altre versioni installate conservate, import di verifica, configurazione
atomica privata, niente aggiornamento di configurazione su fallimento o modifica
concorrente. Nessuna installazione reale di Demucs è stata eseguita nel runner.

Payload DEB di prova costruiti e controllati con esito positivo e negativo anche
quando manca l'installer Demucs. Ricette RPM/DEB aggiornate. Nessun nuovo RPM reale
costruito/installato o servizio reale riavviato da questo ambiente.

## Risultato intermedio

Il primo passaggio completo ha trovato due fixture di recupero stems incomplete:
simulavano file_path e load_project ma usavano un id fittizio non valido per il
nuovo controllo del percorso fisico. È stato completato il mock del root del
progetto; restano tutte le asserzioni su progetto errato, opzioni invalide,
sorgente mancante e cancellazione. Log/XML del passaggio integration sono inclusi.
Nessun controllo della produzione è stato rimosso per adattarsi alle fixture.

## Stato funzionale e limiti

L'utente conferma la generazione completa AI Arranger sul server. Le precedenti
conferme su prova breve, annullamento e persistenza rimangono valide per quelle
build. Non sono state svolte nuove inferenze AMD/ROCm, download YouTube reali,
installazioni native macOS/Windows, prove SMTP reali o collaudi browser hardware
in questo runner. La nuova build va sottoposta alla CI e al collaudo operativo.

SERVER_MEDIA_AND_VALIDATION_R210.md contiene il comando per installare/abilitare
Demucs nel runtime ROCm disponibile e la checklist residua del server. La presenza
della GPU non abilita da sola una build Torch CPU. La coda AI non certifica il
metering: profiler, agent Proxmox e DRM restano diagnostici e non fatturabili.
Nessuna tariffa modificata. Per il billing GPU servono provider per job verificato,
copertura completa, prove di concorrenza/errori e persistenza dell'evidenza nel
ledger; questo lavoro non è dichiarato completato.

Messaggio Git cumulativo suggerito (include i due cicli precedenti non committati):
Add AI job management, native ACE setup, shared tokens, usage reports and email summaries; fix YouTube imports, queued web stems and media cleanup
