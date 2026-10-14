# MTA Audio Editor r208 — Analisi Lyrics/Chords fuori dal lock

Il worker di separazione stem calcola Lyrics e Chords senza trattenere il lock cross-process del progetto durante l'inferenza locale o remota. Dopo l'elaborazione acquisisce il lock, ricarica la versione più recente del progetto e salva solo se le rispettive annotazioni sono ancora vuote. Se sono state inserite annotazioni nel frattempo, la fase facoltativa di enrichment fallisce in modo non distruttivo e viene riportata nello stato del job; gli stem già pubblicati restano disponibili.

Il controllo usa una politica conservativa: in presenza di annotazioni preesistenti non tenta fusioni automatiche. Restano da collaudare i job su GPU e la concorrenza reale tra più istanze server.
