# MTA Audio Editor 0.3.0-r208 — AMD SMI su EL10

Il repository ufficiale AMD ROCm 7.2.4 per EL10 fornisce `amd-smi-lib`, non `amdrocm-amdsmi`. L'installer usa il pacchetto corretto da `mta-rocm-userspace`, disabilitando EPEL esclusivamente nella transazione, mantenendo le firme GPG e senza usare `--allowerasing`. In caso di pacchetto indisponibile/fallimento, l'errore viene segnalato; non vengono scaricati RPM arbitrari o script non verificati. Il test di telemetria effettivo resta da eseguire su hardware EL10.

Default wizard nuove installazioni: ACE-Step `local`; configurazioni/checkpoint esistenti preservati.
