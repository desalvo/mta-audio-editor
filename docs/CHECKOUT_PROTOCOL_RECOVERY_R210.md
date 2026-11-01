# Checkout provider protocol and recovery — r210

Base confermata: commit ee4e37fd30c39a72638b303b01ca0cd5b090f272, full CI 41156985339 verde. Il cumulativo include tutti i delta successivi non dichiarati committati: risposte malformate, quote esatte, piano RC e modifiche di questo batch.

Stripe non conferma più identificativi di sessione vuoti o incongruenti. Gli adattatori HTTP Stripe e PayPal rifiutano JSON non valido o non costituito da oggetto con errori gestiti. I retry di creazione continuano a restare incerti dopo il primo tentativo e non effettuano una seconda richiesta.

Il recupero autenticato PayPal rifiuta collegamenti di approvazione malformati, ambigui, a host non ammessi o con controlli/porte/credenziali non validi. In assenza di un collegamento di approvazione il recupero dell'identificativo resta possibile; non implica pagamento né accredito. La validazione dei link riusa quella del checkout originale. Le prove di provider, identità e stato rimangono necessarie.

Regressioni: 100 test della suite checkout/recovery/quote/PayPal e 18 test protocollo HTTP, di cui 15 sovrapposti alla suite da 100; 175 test aggiuntivi riconciliazione Stripe/PayPal, storico, rimborsi, perdite sottoscrizioni e security review. Totale 278 casi distinti passati. Ruff, SAST 309 sorgenti con 168 finding identici (0 HIGH), inventari AI, admission e remote superati. Nessun provider reale o nuova CI utilizzati; non si dichiara la chiusura di A5 né una verifica sandbox.

La richiesta di un batch di almeno 20 cicli sostanziali resta aperta: questo checkpoint non equivale a 20 cicli. RC invariata 32/42 = 76,2% sul perimetro precommercial-20261030. Proseguire con i restanti esiti A4/A5 e i filoni indipendenti del piano RC_ACCELERATION_20261101_R210.md.

Commit suggerito: Harden checkout recovery and prioritize RC acceptance
