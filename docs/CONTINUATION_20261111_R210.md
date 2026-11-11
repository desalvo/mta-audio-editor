# MTA Audio Editor — ripresa dalla chat Work #17

Aggiornato: 11 novembre 2026. Versione **0.3.0-r210**, **PRE-RC 73%**.

## Sorgenti e decisioni recuperate

- Repository: `desalvo/mta-audio-editor`, branch `main`.
- Base verificata: `6dae37ec8128e07aeb59e20798c7e68ea7193daa`.
- Archivio completo: `MTA-0.3.0-r210-bs-roformer-bass-cumulative.zip`,
  102361815 byte, SHA-256
  `3ae1e462c890a0b85372d21d0ef4a06f11ec0e0b9d093e91151907b8d6828a64`.
  Checksum e CRC dei 5434 elementi verificati. Nessun file tracciato o
  permesso eseguibile della base è perso.
- L'utente autorizza commit e push diretti su main e avvio full CI. Le vecchie
  istruzioni degli handoff che vietavano i commit sono superate.
- Messaggio concordato: `Add optional verified BS RoFormer bass separation [full-ci]`.
- Conservare AI legacy, SDK VST, sorgenti, documentazione, test e licenze.
  Mantenere versione e modalità non commerciale; nessun tag o release richiesto.
- Demucs resta predefinito. BS RoFormer è opzionale e la policy è disabilitata
  finché non viene completata la revisione documentata dei diritti per il
  deployment. Distinguere sempre licenze del codice e dei checkpoint.
- Ambiente utente: Rocky 10.2, ROCm 7.2.4, Torch `2.15.0.dev+rocm7.2`,
  AMD Strix Halo. Non confonderlo con il runtime locale di sviluppo.

## Modifiche completate

Recuperati profili BS RoFormer basso + accompagnamento e quattro stem,
installer CPU/CUDA/ROCm con sorgenti e hash fissati, gestione runtime e pesi
separati, integrazione server/native/iOS, intervalli timeline, dossier licenze,
manuali amministratore IT/EN e relativi test della chat #17.

Corretto il runtime: un accompagnamento già presente lasciava il basso appena
scritto nella cartella di uscita. Ora tutti i WAV vengono preparati prima della
pubblicazione; collegamenti esclusivi impediscono sovrascritture, e gli errori
gestiti rimuovono soltanto i file creati dall'operazione. Device e inode
proteggono i file sostituiti da un altro writer. Annullamento, revoca dei diritti
e callback finale fallita attivano il recupero. Sono rifiutati input vuoto/non
finito e overflow float del residuo. Nessuna normalizzazione indipendente.

I percorsi vengono restituiti soltanto dopo i controlli finali. Sono necessari
hard link supportati dal filesystem. Non è dichiarata atomicità dell'intero
gruppo in caso di morte del processo o perdita di alimentazione; resta attiva
la transazione di registrazione del progetto.

Le modifiche erano state raccolte nel commit locale `64517cb`, mai pubblicato
per il precedente rifiuto automatico. Dopo l'autorizzazione esplicita l'ambiente
ha perso il checkout: codice e test sono stati ricostruiti dall'archivio
verificato e dalle patch della conversazione. Il nuovo commit avrà un hash
diverso, senza recuperare il vecchio oggetto Git non più disponibile.

Validazione corrente dopo il ripristino: 214 test distinti passati, di cui 80 basso/default e
134 amministrazione, policy, selettori e inventari. Sono inclusi 11 nuovi casi
su collisioni, symlink, errori disco, annullamento, revoca, callback e audio
non finito. Le stesse prove sono passate anche dopo il ripristino (214 passati, zero fallimenti o skip). Ruff e sintassi
JS passano. Bandit: 191 finding (170 LOW, 21 MEDIUM, zero HIGH), nessuna
soppressione o nuova identità. Censimento dei confini di esecuzione, trasporto
e ammissione invariato; aggiornare solo le identità riesaminate e la scansione.

## Conservazione richiesta dall'utente

Mantenere sempre in ChatGPT Library `MTA-Audio-Editor-HANDOFF-current.md`,
aggiornandone la stessa identità dopo ogni batch, e conservare ogni cumulativo
contenente modifiche non ancora pubblicate con commit verificato. Salvare un
checkpoint prima di fermarsi o chiedere un'autorizzazione. Non affidarsi al
checkout temporaneo. Nell'handoff includere archivio/checksum, commit locale
e remoto, CI con URL e stato, risultati, configurazione, autorizzazioni,
priorità e limiti. Dopo il push aggiornare l'handoff con gli identificativi
effettivamente restituiti. Non eliminare l'unica copia di lavoro non pubblicata.

## Prossimi passi

1. Pubblicare il commit approvato e verificare la full CI sul suo SHA.
2. Completare revisione diritti, installazione sul nodo effettivo, inferenza
   CPU/GPU e confronto A/B a pari livello contro Demucs sullo stesso input.
3. Per cori/duetti/sovraincisioni: audit dei singoli checkpoint Karaoke,
   MedleyVox e UNMIXX. Il dossier
   `BASS_SEPARATION_AND_VOCAL_CANDIDATES_R210_IT_EN.md` distingue i casi.
   Sono candidati, non backend nuovi attivati. Non dedurre una licenza dai
   soli dati del model card o dalla licenza del dataset.
4. Nessuna promozione RC da test sintetici: rimangono prove reali di modelli,
   ascolto, GPU, sistemi installati e gli altri blocchi RC già documentati.

Leggere le ultime sezioni datate di `DEVELOPMENT_STATUS.md` prima dei vecchi
documenti di coda: percentuali e istruzioni storiche possono essere superate.
