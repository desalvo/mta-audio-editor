# r208 — resoconto non distruttivo dei file preservati nel recovery stem

Durante la riconciliazione di un journal stem incompleto, il sistema espone ora:
- `removed`: file riconosciuti come proprietà della transazione e rimossi.
- `preserved_unowned`: nuovi file non registrati come proprietà, deliberatamente conservati.
- `preserved_replaced`: file non più corrispondenti all'identità/forma attesa, deliberatamente conservati.
- `errors`: journal che richiedono intervento manuale.

I conteggi sono aggregati anche dal recovery all'avvio e registrati nel log già previsto dal server. La conservazione di un file non ne implica l'importazione automatica e non autorizza cancellazioni successive. I journal storici mantengono il precedente trattamento. Una pubblicazione interrotta tra creazione e registrazione inode può lasciare file orfani: sono conservati intenzionalmente.

Verifica locale: 17 test dedicati ai journal, allo startup e ai recovery stem superati. Non certifica la suite globale o i crash fisici su altri filesystem.
