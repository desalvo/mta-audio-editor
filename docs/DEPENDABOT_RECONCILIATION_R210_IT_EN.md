# MTA r210 — revisione delle PR Dependabot / Dependabot reconciliation

11 novembre / November 2026. Base verificata / Verified base: `b314301`.

## IT

GitHub presenta sei PR aperte, comprese le due proposte più vecchie per h5py e
beartype. La revisione integra quattro proposte in una sola modifica verificata
prima del merge su main. La cronologia conserva le punte delle PR integrate.

| PR | Decisione | Motivo e correzioni |
|---|---|---|
| #16 h5py | Integrare | Minimo 3.16.0. Il precedente installer macOS Intel verde già installava h5py 3.16.0. Aggiunto round-trip HDF5 reale con array float32 compressi e metadati UTF-8. |
| #18 beartype | Integrare | Linea 0.23.1–0.23.x; allineati requisito e due override dei build nativi. Conservati gli smoke PEP 604; aggiunti test del validator e del decorator reali su Callable o None e valori rifiutati. |
| #28 Android | Integrare | ONNX Runtime 1.31.1 e AGP 9.5.1. Gradle 9.6.0 e API 37 esistenti corrispondono alla matrice ufficiale AGP 9.5. Aggiornati i due test di versione. |
| #33 Actions | Integrare | Aggiornamenti delle action ufficiali e Docker; riparati due test che cercavano upload-artifact v4 dopo il passaggio a v7. Il resto dei controlli su sorgenti, autorizzazioni e firma resta attivo. |
| #32 Python 3.15 | Chiudere senza merge | La build container fallisce nella compilazione SciPy per assenza di un compilatore Fortran; la migrazione richiede una verifica coordinata dei wheel e runtime, oltre al cambio del tag Docker. Resta Python 3.14. |
| #34 gruppo Python | Chiudere senza merge | Cambia torchvision 0.17.2 del vecchio Torch Intel 2.2.2 in 0.29.2+cpu e modifica freeze storici senza rieseguire gli ambienti. La CI segnala sette fallimenti. Le singole proposte compatibili potranno essere rivalutate separatamente. |

Le vecchie ricevute di test e i freeze in `validation/` non vengono riscritti:
rappresentano ambienti realmente eseguiti. Dependabot li esclude insieme alle
dipendenze vendorizzate. Torch, torchaudio e torchvision sono un insieme da
rivedere manualmente; le nuove linee minori/maggiori Numba, llvmlite, SciPy e
contourpy richiedono revisione delle ricette. Le proposte patch restano abilitate
per questi quattro pacchetti. Anche le nuove linee Python Docker vengono
rinviate a una migrazione coordinata; gli aggiornamenti patch restano possibili.

Le dipendenze dei due nuovi contratti sono installate nella suite Quality:
un test saltato per assenza di h5py/beartype non costituirebbe verifica.
Le prove locali usano Python 3.12; la CI deve confermare Python 3.14 e i build
nativi. Nessun modello neurale o ascolto reale viene certificato da questi test.
Il runtime BS RoFormer separato mantiene la propria ricetta fissata a beartype
0.22.5: non è lo stesso ambiente degli override delle app native.

## EN

Six open proposals were reviewed. Integrate #16, #18, #28 and #33 together with
their compatibility fixes; reject #32 and #34 in their current form. The four
accepted PR heads remain in the integration history. h5py now requires 3.16.0,
already used by the previous successful Intel macOS build. Real HDF5 and
beartype contracts run in Quality; native overrides and pinned-version tests
are aligned with the accepted versions.

The Android update retains Gradle 9.6.0 and API 37, matching the official AGP
9.5 compatibility matrix. Two artifact tests must expect upload-artifact v7.
Python 3.15 currently fails the container gate; the broad Python batch breaks
the Intel Torch/torchvision family and rewrites historical freezes. Neither
proposal should be merged as-is. Historical evidence and vendored recipes are
excluded from automatic scans, while coupled runtime families and Python
minor/major migrations receive explicit review. Patch proposals remain allowed
for Numba, llvmlite, SciPy, contourpy and the Python Docker image.

Local tests use Python 3.12. CI must confirm Python 3.14 and native build
acceptance. These checks do not certify actual neural inference or audio
quality. The separate BS RoFormer recipe keeps its own beartype 0.22.5 pin.

## Fonti / Sources

- [PR MTA](https://github.com/desalvo/mta-audio-editor/pulls)
- [AGP 9.5 compatibility](https://developer.android.com/build/releases/agp-9-5-0-release-notes)
- [Dependabot options](https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-options-reference)

## Verifica della cronologia / History scan

La prima CI della PR35 rileva un solo falso positivo: il digest pubblico di
`app/auth.py` nel ledger del commit storico `e54f7113`. Il sorgente esatto è
stato riletto da GitHub e SHA-256 ricalcolato, uguale al valore segnalato.
Il dossier GITLEAKS_REVIEW_R210 registra fonte e prova; l’eccezione identifica
soltanto commit, file, regola e riga. La scansione predefinita resta attiva.

The first integration scan flags one historical public source digest. The
exact source was retrieved and its SHA-256 recomputed. The review records the
proof and restricts the exception to that commit/file/rule/line; default
secret scanning remains enabled.
