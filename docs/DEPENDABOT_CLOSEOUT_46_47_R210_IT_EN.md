# Chiusura Dependabot46/47 — 12 novembre 2026 / Closeout

## Italiano

Base verificata: main62c3643, full CI43219262885 verde con9084 test passati,
126skip,copertura78,31%,Dockerlatest e bundleearly-main pubblicati.
Due nuove PR sono state valutate separatamente dai controlli generici verdi.

| PR | Esito | Verifica |
| --- | --- | --- |
| #46 Setuptools 84.2.1 | Integrare | Ambiente Basic Pitch nuovo e isolato, con inferenza ONNX reale tramite self-test MTA |
| #47 Transformers 5.22.2 | Chiusa senza merge | Richiede huggingface-hub>=1.31.0,<3.0, incompatibile con hub==0.36.2 della conversione |

La #47 cambia insieme conversione4.46.3,YourMT34.57.6 eMR-MT35.13.1.
Si conservano le tre ricette verificate; una migrazione4→5 richiede revisione
coordinata diHub,Torch e interfacce dei checkpoint. Aggiunta la revisione
manuale delle major Transformers alla policy Dependabot; patch/minor restano
proponibili. Il corpo della PR riporta la ragione concreta della chiusura.
La CI server verde non installa quei runtime opzionali e non risolve il
conflitto tra i pin dichiarati.

Per la #46 è stato creato un virtualenvPython 3.12 pulito, installando la
ricetta Basic Pitch con Setuptools 84.2.1 e basic-pitch0.4.0--no-deps come
nell'installer. Nessun runtime di produzione è stato sostituito.
Il self-test **originale MTA**, invocato con Python -I, ha verificato il modello
ONNX con SHA256
`2c3c1d144bfa61ad236e92e169c13535c880469a12a047d4e73451f2c059a0ec`,
eseguito inferenza CPU e restituito **1 nota** corrispondente alLa 440/MIDI 69
del segnale sintetico di due secondi.

Versioni effettive: Setuptools 84.2.1,Basic Pitch0.4.0,NumPy 1.26.4,
ONNX Runtime 1.31.1. pkg_resources è assente nel nuovo Setuptools; il self-test
è comunque riuscito con le dipendenze effettive della ricetta. La rimozione
upstream da82.0 non viene quindi usata come motivo ipotetico di rifiuto.
Freeze e provaJSON sono conservati nel cumulativo sotto validation/r210/.

Questa prova verifica la compatibilità dell'installazione e l'esecuzione del
backendCPU; non misura accuratezza musicale generale, più strumenti, GPU,
latenza hardware o ascolto. Non è una promozioneRC.
La nuova fullCI sullo SHA integrato deve ancora completarsi.

Validazione aggiuntiva: **16 test di regressione passati**, zero fallimenti
o skip; Ruff completo e whitespace passano.

## English

Accept #46 after a fresh isolated Python 3.12 installation and the original MTA
Basic Pitch ONNX self-test with Setuptools 84.2.1. The pinned checkpoint hash
matches and CPU inference returns the expected MIDI 69 note. NumPy remains
1.26.4 and ORT1.31.1; no installed production environment is replaced.

Close #47 without merging: Transformers 5.22.2 requires Hub>=1.31.0,<3.0,
contradicting the conversion recipe's Hub 0.36.2 pin. Preserve conversion4.46.3,
YourMT34.57.6 andMR-MT35.13.1. Major Transformers upgrades now require a
coordinated manual recipe review. Green generic CI does not test these
optional environments.

The inference is a two-second synthetic installation check, not a music
accuracy/hardware acceptance claim. Final main CI and packaging remain to
be verified; version0.3.0-r210 / PRE-RC 73% unchanged.

## Fonti primarie / Primary sources

- [Transformers 5.22.2 dependency metadata](https://github.com/huggingface/transformers/blob/v5.22.2/setup.py)
- [Transformers 5.22.2 published metadata](https://pypi.org/project/transformers/5.22.2/)
- [Setuptools 84.2.1 changelog](https://github.com/pypa/setuptools/blob/v84.2.1/NEWS.rst)
- [Basic Pitch0.4.0 source](https://github.com/spotify/basic-pitch/tree/v0.4.0)

