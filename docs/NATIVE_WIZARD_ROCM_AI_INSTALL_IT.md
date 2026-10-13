# Wizard nativo: AMD ROCm e ACE-Step (r208)

L'installazione del server MTA avviene tramite pacchetti firmati RPM/DEB. Nel wizard, selezionando ACE-Step `local`, viene verificato l'accesso a `/dev/kfd` e a un dispositivo `/dev/dri/renderD*`. Se il runtime ROCm non è funzionante, l'installer del pacchetto tenta di installare automaticamente **solo componenti userspace** dai repository già configurati. Su EL9 può configurare il repository AMD ROCm esplicitamente previsto dal progetto; su EL10 non utilizza mai repository EL9, ma propone le istruzioni ufficiali se non sono disponibili pacchetti compatibili.

Documentazione ufficiale ROCm: https://rocm.docs.amd.com/projects/install-on-linux/en/latest/

L'installer non installa driver kernel in VM/LXC; per questi è necessario esporre i dispositivi GPU dal sistema host, configurare passthrough e permessi. Qualora il runtime non possa essere inizializzato, ACE-Step locale non viene installato: il wizard spiega come ripristinare il prerequisito e suggerisce il backend remoto. GPU AMD e supporto ROCm devono essere compatibili con la specifica distribuzione e versione ROCm. Non vengono disabilitate le verifiche GPG. Il tool `amd-smi` è opzionale per il calcolo ROCm, ma necessario se si vogliono abilitare alcune forme di telemetria/accounting.

Dopo la configurazione della GPU, controllare `rocminfo` e quindi eseguire `sudo bash install_mta.sh --configure-only`. Per installazioni unattended è preferibile configurare prima l'ambiente GPU sul sistema host; il wizard non abilita repository di terze parti non supportati sul proprio OS.

I certificati autofirmati sono esclusivamente una soluzione per test/ambienti controllati. In produzione fornire certificato CA valido e relativa chiave privata.
