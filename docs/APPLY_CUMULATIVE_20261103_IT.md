# Applicazione del pacchetto cumulativo

Estrarre il pacchetto sulla copia di lavoro, preservando le modalità eseguibili. Per eliminare anche i due file SAM Audio ritirati, dall'interno del repository eseguire:

```sh
git rm --ignore-unmatch app/sam_audio_worker.py app/sam_audio_compat.py
```

La semplice estrazione di un archivio non elimina i file preesistenti. Verificare `git status` e i controlli CI prima del rilascio. Dataset rigenerabili, registrazioni di terzi e pesi dei modelli non sono inclusi.
