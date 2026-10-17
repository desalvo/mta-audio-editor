# Stem server: codec audio e diagnostica — 0.3.0-r210

La diagnostica del 17 ottobre 2026 conferma un job stem-separation fallito con exit code 1 e categoria worker_exit. Non contiene messaggi o traceback del worker: la causa specifica di quella esecuzione non è ricostruibile dallo ZIP. L'utente conferma invece che lyrics/chords/markers e il comportamento dei popup sono ora funzionanti.

## Lacuna corretta

L'installer installava TorchCodec per SAM ma non per il gruppo audio/Demucs. Da TorchAudio 2.9, le funzioni load e save dipendono da TorchCodec; Demucs usa torchaudio.save per pubblicare i WAV. Con TorchAudio 2.11 presente nel runtime ROCm, il solo import di demucs non dimostra che sia possibile leggere o salvare gli stem.

TorchCodec ora viene installato esplicitamente per entrambi i gruppi. Su ROCm viene vincolata la build CPU 0.11.1+cpu compatibile con Torch 2.11; su CPU 0.17.0+cpu e su CUDA 0.17.0 con i vincoli Torch già esistenti. La scelta CPU del codec non sposta il modello Demucs dalla GPU: riguarda l'I/O dei file. Le verifiche precedenti su import, nms e tensore GPU restano attive.

Prima della pubblicazione del runtime viene eseguita una decodifica WAV e una prova torchaudio.save/load con due canali, 1600 campioni e sample rate 16000. Un errore impedisce la creazione del marker ready e il commit dei binding di configurazione. La modifica del fingerprint crea un nuovo runtime senza mutare gli ambienti attivi.

Questa è una lacuna riprodotta dai test, non una conferma retrospettiva della causa del singolo job allegato. Non è stata eseguita un'inferenza Demucs reale su ROCm in questo ambiente di sviluppo.

## Diagnostica sicura

I nuovi errori esportano, oltre alla categoria e all'exit code, solo nomi di eccezioni e dipendenze appartenenti a liste fisse. Ad esempio un ImportError TorchCodec seguito da CalledProcessError del wrapper conserva entrambi i tipi; un modulo mancante noto può comparire come missing_dependency. Sono state aggiunte categorie codec mancante/non caricabile. Le categorie esistenti ROCm/dispositivo e GPU OOM vengono ora ammesse coerentemente nel bundle.

Non vengono esportati stderr arbitrari, traceback, prompt, token o percorsi del worker. Metadata falsi o non appartenenti alle liste consentite vengono scartati. metering_valid resta sempre false per questi errori. Nessun controllo cgroup, di accounting o di fatturabilità viene disabilitato.

## Applicazione e validazione

Dopo compilazione e installazione del nuovo RPM, dalla root del progetto:

```bash
sudo bash scripts/install_mta.sh --configure-only --unattended
```

È necessario completare il provisioning: aggiornare soltanto l'RPM senza rieseguire setup non installa la nuova dipendenza negli ambienti isolati precedenti. Poi riprovare una separazione breve. Se fallisce, il nuovo ZIP conterrà più informazioni strutturate; per eccezioni non riconosciute resta necessario il journal server.

Test: selezione codec per entrambi i gruppi CPU/ROCm, blocco del preflight in caso di encoder non funzionante, errore annidato, conservazione della dipendenza mancante nel bundle e rifiuto di metadata arbitrari. Regressione generale e risultati in validation/r210-stem-codec-*.

Fonti ufficiali consultate: https://docs.pytorch.org/audio/stable/generated/torchaudio.save_with_torchcodec.html e https://github.com/facebookresearch/demucs/blob/main/demucs/audio.py.

Questo ciclo è successivo al commit confermato dall'utente il 17 ottobre alle 16:08, relativo al precedente ZIP lyrics/device/notifications. Versione invariata; nessuna operazione Git o sul server reale.

## Help installer

Corretto il nome pubblico nell'help delegato al helper nativo: ora mostra install_mta.sh. --help e -h sono opzioni esplicite, terminano con codice 0 e non raggiungono provisioning, rete o controlli root. Gli argomenti sconosciuti restano errori con codice 2 e usage su stderr. Verificati entrambi gli entrypoint e l'help legacy; modifica arrivata dopo la regressione completa, validata separatamente con esecuzione reale dei comandi help.
