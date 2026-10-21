# R210 — Native dependency security CI remediation / Sicurezza dipendenze native

## Italiano
La CI Python 3.14 ha segnalato PYSEC-2026-4320 (certifi 2026.7.22) e PYSEC-2026-4321 (uv 0.12.23) durante `pip-audit -r requirements-native.txt --strict`. Aggiornati i pin a certifi 2026.10.19 e uv 0.13.4, versioni di correzione indicate dall’audit e confermate pubblicate su PyPI (20 ottobre 2026). Le dipendenze native ALSA/JACK e gli altri audit rimangono invariati. La CI completa non è stata eseguita qui; è necessaria conferma da GitHub Actions. Versione MTA 0.3.0-r210 immutata.

## English
Python 3.14 CI reported PYSEC-2026-4320 (certifi 2026.7.22) and PYSEC-2026-4321 (uv 0.12.23) during `pip-audit -r requirements-native.txt --strict`. Requirement pins were raised to certifi 2026.10.19 and uv 0.13.4, the audit's fixed versions, both published to PyPI on 20 October 2026. ALSA/JACK native dependencies and all other strict audits remain unchanged. Full CI has not run here; GitHub Actions must confirm. MTA stays 0.3.0-r210.
