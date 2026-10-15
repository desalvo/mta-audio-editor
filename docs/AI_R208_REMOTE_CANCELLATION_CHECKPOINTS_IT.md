# r208 — checkpoint di cancellazione remota

La cancellazione viene ora propagata dal worker durevole Arranger/Remix al bridge contabile e al client HTTP remoto.
I checkpoint sono eseguiti prima della richiesta POST, prima del recupero GET e prima dell'accettazione del risultato e delle evidenze contabili. Un evento di cancellazione non provoca fallback locale o duplicazione della richiesta. I percorsi senza evento preservano il contratto precedente.

**Limite tecnico:** il trasporto HTTPS sincrono attualmente non interrompe immediatamente una lettura di rete bloccata e non invia un comando di cancellazione al processo remoto. La cancellazione locale è quindi cooperativa e non certifica la cessazione dell'inferenza sul worker remoto. Sono ancora richiesti un protocollo di cancellazione remota autenticato e il collaudo reale.

Non viene rivendicato il completamento dell'intera integrazione AI o del metering GPU.
