# Revisione major Dependabot — 12 novembre 2026 / Major review

## Italiano

Base main verificata: `858dea2392c9e5a40081d5e2e639ddc04624e810`.
La full CI [43137364247](https://github.com/desalvo/mta-audio-editor/actions/runs/43137364247)
è terminata **success**: 9076 test passati,126 saltati, copertura78,31%.
Installer Windows/macOS Intel/arm64/Linux x86_64/arm64, Android/iOS, container,
Docker Hub e pubblicazione rolling early-main sono riusciti. Docker latest
ha digest `sha256:90a53e00449988042f0ed0936b1ddfe56c2686228758b661cc1a13084b230d04`.
Questi risultati attestano la base, non le nuove modifiche elencate qui.

| PR | Aggiornamento | Decisione verificata |
| --- | --- | --- |
| #41 | PyAV 19.0.2 | Integrare: CI e matrice server verdi; filtri audio reali verificati anche con NumPy 1.26.4 |
| #42 | NumPy 1.26.4 → 2.5.4 in nove manifest | Chiusa senza merge della migrazione generale; estratta solo la patch server 2.5.3 → 2.5.4 |
| #43 | websockets 17.4 | Integrare con correzione della fixture ACE-Step; verificati entrambi i backend Uvicorn su socket reali |
| #44 | smart-open 9.0.2 | Integrare: CI verde, verifiche locali UTF-8/gzip e HTTP Range/ETag |
| #45 | reportlab 5.1.0 | Integrare: CI e matrice server verdi, PDF reali e anteprima rasterizzata verificati |

NumPy1.26.4 resta intenzionalmente nei runtime Intel/Basic Pitch/conversione/
DiffSinger/YourMT3. Il test macOS della #42 segnalava una rottura del contratto,
non un controllo da aggiornare alla cieca. Il server può ricevere la sola patch
2.5.4; il suo test installer controlla ora il pin e l'intervallo compatibile,
senza fallire per ogni nuova patch valida. Le major NumPy sono passate alla
revisione manuale; patch/minor server restano proponibili.

L'unico fallimento CI della #43 era nel test ACE-Step: il worker sintetico
pubblicava il file progress con write_text, e il thread di annullamento si
attivava alla sua sola esistenza, prima che il task ID fosse necessariamente
scritto. La fixture usa ora file temporaneo e os.replace come il vero adapter.
Il controllo resta una terminazione reale di subprocess con esattamente un
annullamento HTTP al task remoto. Nessun timeout prolungato, skip aggiunto o
codice di esecuzione/ammissione modificato.

PyAV19 richiede Python>=3.12, coerente con server e build native supportati;
sono disponibili wheel macOS Intel e arm64. Le proprietà razionali passano ad
AVRational; i setter continuano ad accettare Fraction. I test esercitano il
Filter reale dell'app con mono/stereo, blocchi parziali, flush e guadagno.
La compatibilità NumPy1.26.4 è riprovata separatamente; questo non attesta
l'inferenza di tutti i modelli del runtime di conversione.

websockets17.4 include un limite ai frammenti per proteggere la memoria.
La compatibilità con Uvicorn0.54 è verificata su connessioni reali per i backend
websockets e websockets-sansio, con testo JSON/Unicode, frame binari e chiusura.
smart-open9 mantiene la versione HTTP del primo read nelle richieste Range;
risorse cambiate devono fallire con412. Questo comportamento è verificato con
un server locale, senza disabilitare If-Match. Il contratto YourMT3 viene
esercitato nel gate normale tramite smart-open[http] nei soli requisiti dev.

Validazione locale: **52 test distinti passati**, zero fallimenti/skip, con
NumPy2.5.4,PyAV19.0.2,websockets17.4,smart-open9.0.2,ReportLab5.1.0 e
Uvicorn0.54.0 reali. I due casi filtro PyAV sono ripetuti con NumPy1.26.4,
entrambi passati; non sommare le ripetizioni al totale dei test distinti.
Ruff completo app/native/tests/scripts/k8s-wizard.py passa.
La nuova full CI e gli installer vanno verificati sullo SHA finale integrato.
**0.3.0-r210 / PRE-RC73%** invariati, nessuna qualità modelli/ascolto promossa.

## English

The baseline full production CI is green, including all native/mobile builds,
Docker publication and rolling packages. Review the five new PRs separately:
accept PyAV19,websockets17.4,smart-open9 and ReportLab5.1 with targeted real
library contracts; reject the blanket NumPy2 migration while extracting only
the safe server2.5.4 patch and retaining every intentionally pinned NumPy1.26
recipe. Major NumPy migrations require a coordinated manual review.

The WebSockets PR failure came from the synthetic ACE adapter publishing a
partly written progress file before the cancellation trigger. Match production
atomic publication in the fixture; preserve the actual process termination
and HTTP cancellation assertion. Production worker/admission code is unchanged.

52 distinct local tests pass with the real new versions. These include live
Uvicorn WebSocket text/binary connections, real PyAV block filters, UTF-8/gzip
model metadata, HTTP Range version integrity, app PDF generation/preview,
cancellation and Intel policy guards. Repeat the two real PyAV filter cases
under NumPy1.26.4; both pass. Full scoped Ruff passes. Final main CI and native
packages remain to be verified; no model inference/listening certification.

## Fonti primarie / Primary sources

- [WebSockets17.4 changelog](https://github.com/python-websockets/websockets/blob/17.4/docs/project/changelog.rst)
- [smart-open9 migration guide](https://github.com/piskvorky/smart_open/blob/v9.0.2/MIGRATING_FROM_OLDER_VERSIONS.md)
- [PyAV19.0.2 release](https://github.com/PyAV-Org/PyAV/releases/tag/v19.0.2)
- [PyAV19.0.2 wheels/metadata](https://pypi.org/project/av/19.0.2/#files)
- [ReportLab5.1.0 metadata](https://pypi.org/project/reportlab/5.1.0/)

