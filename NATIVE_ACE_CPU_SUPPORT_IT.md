# ACE-Step locale: CPU-only e AMD ROCm (MTA 0.3.0-r208)

Il wizard nativo offre ACE-Step locale anche senza GPU. Scelta `auto` = ROCm se i dispositivi AMD sono accessibili, altrimenti CPU; `cpu` forza CPU; `rocm` richiede GPU AMD accessibile. Se il provisioning ROCm non riesce, il wizard può ricadere su CPU, con messaggio di avviso sulle prestazioni. L'installazione conserva modelli e dati persistenti.

```bash
sudo bash install_mta.sh --configure-only
# Installer ACE-Step fornito dal package:
sudo bash /usr/lib/mta-audio-editor-server/native-installers/install_ace_step.sh --device cpu --yes
```

CPU-only usa i wheel ufficiali PyTorch CPU e installa il progetto ACE-Step nello stesso venv; `pip check` e un controllo torch CPU bloccano errori di dipendenza prima di sostituire la precedente installazione. Il servizio systemd locale ascolta su loopback per impostazione predefinita. Si raccomanda `ACESTEP_INIT_LLM=false` per la modalità CPU/DiT-only, già presente nella configurazione iniziale prodotta dal wizard.

**Nota di validazione**: controllo shell, dry-run CPU senza GPU e test strutturali automatizzati sono superati. Non sono stati eseguiti il download integrale ACE-Step, l'inferenza CPU reale e lo smoke HTTP su macchina di destinazione. È necessario un collaudo su EL10 reale prima di dichiarare la funzionalità certificata.
