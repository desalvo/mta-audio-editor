# EL10 ACE-Step Python installer refinement (0.3.0-r208)

EL10 supplies Python 3.12 as `python3` and pip as `python3-pip`; `python3.11` is not required. The ACE-Step installer uses that distribution Python on EL10 unless `MTA_PYTHON` is explicitly set. EL9 and Debian paths retain their original interpreter defaults. ACE-Step Python dependencies are isolated in `/opt/mta/venv-ace-step`; no `pip install` is run against the system Python. The installer rejects interpreters outside 3.11–3.12.

Local checks do not replace real EL10/ROCm installation tests.
