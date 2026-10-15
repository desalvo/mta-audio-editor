# MTA Audio Editor 0.3.0-r208 — chiusura identità nomi stem cross-platform

Il produttore di ZIP AI e il consumer di importazione stem rifiutano nomi che differiscono solo per maiuscole/minuscole, prevenendo collisioni sui filesystem case-insensitive. Sono preservate le verifiche di digest, manifest e pubblicazione transazionale preesistenti. Rifiuto prima della modifica del progetto.

## Verifica software
- 31 test integrati dei percorsi stem: superati.
- Suite `tests/test_r208_*`: 1183 superati, 13 warning, zero fallimenti (36,59 s).
- Non certifica la regressione globale non-r208 o i runtime Windows/macOS reali.
- VERSION e REVISION invariati; nessuna operazione Git.
