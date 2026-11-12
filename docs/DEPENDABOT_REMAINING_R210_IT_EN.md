# Dependabot: remaining Python PRs — r210 / 12 November 2026

## Italiano

Base verificata: main `9f51f615eb7d80a37294ef08622c33ffd042591a`, produzione
verde nel tentativo 2 della run 43085554260. Versione 0.3.0-r210,
PRE-RC globale 73% invariata.

| PR | Decisione | Motivo |
| --- | --- | --- |
| #36 | Integrare con le correzioni elencate sotto | 17 aggiornamenti minor/patch; la CI originale aveva 8684 passati e cinque fallimenti |
| #38 | Integrare il renderer ufficiale PyMuPDF-lite 2.1 | Stesse API PDF; wheel Intel conservato, mentre il pacchetto completo 2.1 ha solo wheel macOS arm64 |
| #39 | Integrare tqdm >=4.70.1,<5 | CI originale verde, aumento del limite minimo entro la stessa major |
| #40 | Integrare six >=1.17.0,<2 | CI originale verde; allineato anche il comando manuale Windows |
| #37 | Chiudere senza integrare huggingface-hub 2.4.0 | transformers 4.46.3 richiede huggingface-hub>=0.23.2,<1.0 nel runtime isolato di conversione |

La CI verde di #37 non installa il runtime opzionale di conversione: non prova
la compatibilità dei suoi pin. Conservato huggingface-hub 0.36.2 e aggiunta
la revisione manuale delle major hub alla policy Dependabot. Le patch/minor
compatibili restano proponibili. Non è stata disabilitata la scansione sicurezza.

Il gruppo #36 aggiorna pytest 9.2.0, pytest-asyncio 1.4.1.post1, Ruff 0.17.4,
truststore 0.10.5, certifi 2026.10.23, uv 0.13.7, sounddevice 0.5.6,
msgpack 1.2.4, audio-separator 0.48.0, onnxruntime 1.31.1, resampy 0.4.3,
fastapi 0.162.2, einops 0.8.2, safetensors 0.8.0, deprecated 3.0.1,
python-multipart 0.0.33 e yt-dlp 2026.10.26 nei rispettivi manifest.

Il controllo dei file pubblicati su PyPI ha rilevato che PyMuPDF 2.1 completo
non offre wheel macOS Intel e aggiunge layout/LLM/ONNX non usati dall'app.
La distribuzione ufficiale **PyMuPDF-lite 2.1** contiene le API renderer
fitz/pymupdf necessarie all'anteprima e mantiene wheel Intel e arm64. Viene
usata uniformemente sulle piattaforme supportate, senza retrocedere a 1.28.2.
Il test applicativo rasterizza il PDF reale con questa distribuzione.

La CI combinata su 4ea84d1 ha superato 8689 test (58 saltati), copertura
77,81%, sicurezza/CodeQL/VST3 e tutta la matrice server (7/7). L'immagine
container è stata costruita correttamente con msgpack 1.2.4; un secondo
controllo nel workflow pretendeva ancora 1.2.3 e ha fermato il job prima dei
successivi audit/smoke. Allineato quel controllo senza abbassare la versione
di sicurezza, e aggiunto un test di coerenza tra i manifest e i due checker.
La successiva full CI deve verificare tutti gli step sullo SHA finale.

Correzioni necessarie:

- Docker installa e verifica msgpack 1.2.4 anche nella convergenza finale,
  evitando di ripristinare 1.2.3 dopo l'installazione del manifest.
- Il comando Windows --no-deps usa audio-separator 0.48.0 come Linux/arm64.
  La ricetta macOS Intel resta su audio-separator 0.30.2 e Torch 2.2.2,
  con torchvision 0.17.2; non viene forzata sulla famiglia recente.
- Tre test con versioni esatte obsolete sono allineati alle dipendenze
  riesaminate; non è stato ridotto il perimetro di test o dei gate.
- Il confronto dei segmenti tempo controlla lunghezza e ogni tupla con
  pytest.approx: pytest 9.2 rifiuta la lista annidata passata direttamente.
- La prova del rilascio del lease dopo il fallimento SQLite usa un file flock
  riservato al thread sotto prova. I worker degli altri test continuano a
  usare il percorso originale; i lock reali non sono sostituiti né disattivati.
  Il timeout SQL, il ripristino del busy_timeout e l'acquisizione esclusiva
  immediata dopo il fallimento restano verificati.

Validazione locale: 44 test distinti superati con Python 3.12, pytest 9.2,
pytest-asyncio 1.4.1.post1, FastAPI 0.162.2 e PyMuPDF-lite 2.1; inclusi
FFmpeg reale, export/poll/download autenticati sotto lock esclusivo SQLite,
normalizzazione/tempo e rasterizzazione del PDF dell'app.
Ruff 0.17.4 passa su app/native/tests.
La CI combinata e gli installer sul commit integrato vanno verificati
separatamente; le inferenze reali dei modelli e l'ascolto non sono certificati
da questi test. Il job Dependabot pip 43085563115 (soundfile,
`Expected content to change!`) è distinto dalle cinque PR.

## English

The reviewed patch/minor updates in #36 are combined with the official PyMuPDF-lite 2.1 renderer (#38),
tqdm (#39) and six (#40). Docker's final msgpack pin and the Windows
audio-separator override match the manifests. The legacy Intel audio recipe
remains unchanged. Three stale version assertions are updated, nested tempo
comparisons are checked tuple by tuple, and the failed-connection flock test
isolates its own thread from unrelated background workers while retaining
real SQLite and OS locking.

Reject #37: transformers 4.46.3 explicitly requires huggingface-hub<1.
Keep hub 0.36.2 and review major upgrades together with the conversion recipe.
Existing green generic CI does not validate that optional environment.

The full PyMuPDF 2.1 distribution has no Intel macOS wheel; the official lite
renderer provides both Intel and arm64 wheels and the same PDF rendering API.
MTA uses the lite renderer consistently, without adding unused layout/LLM/ONNX
features. The actual app PDF rasterization test runs against this distribution.

Local verification: 44 targeted tests and full app/native/tests Ruff pass.
Combined CI and native packaging must still be checked on the integrated SHA.
No model quality or hardware acceptance claim; version and PRE-RC status stay
0.3.0-r210 / 73%.

## Primary sources

- [Transformers 4.46.3 dependency metadata](https://github.com/huggingface/transformers/blob/v4.46.3/setup.py)
- [PyMuPDF-lite 2.1 published wheels](https://pypi.org/project/PyMuPDF-lite/2.1/#files)
- [PyMuPDF 2.1 build metadata](https://github.com/pymupdf/PyMuPDF/blob/2.1/setup.py)
- [PyMuPDF release changes](https://github.com/pymupdf/PyMuPDF/blob/main/changes.txt)
- [audio-separator 0.48.0 metadata](https://github.com/nomadkaraoke/python-audio-separator/blob/v0.48.0/pyproject.toml)

