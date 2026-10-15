# MTA 0.3.0-r209 — Ingress HAProxy e ripresa dei job AI

Manifest di esempio: `deploy/remote-ai/kubernetes/mta-haproxy-external-native-example.yaml`.

Sostituire `BACKEND_PRIVATE_IP` con l'IPv4 privato del server RPM e
`mta.example.org` con il DNS scelto. Non pubblicare ACE-Step/8001.

Il controller HAProxy del collaudo non riconosceva il backend con il solo
EndpointSlice manuale: ha risposto HTTP 200 solo dopo la creazione di `Endpoints`
tradizionale. Per compatibilità si usa un Service senza selector con `Endpoints`;
Kubernetes crea il corrispondente EndpointSlice. Non creare un secondo
EndpointSlice manuale per lo stesso backend. Verificare la configurazione quando
si aggiorna il controller: `Endpoints` è un'API legacy deprecata.

Con `secretName` assente l'Ingress può utilizzare il certificato TLS predefinito
fornito dal controller. L'esempio include commentata la sezione TLS Secret.
L'annotazione `kubernetes.io/ingress.class: haproxy` è volutamente presente,
per compatibilità con il controller del collaudo.

Verificare dopo `kubectl apply -f <file>`:

```sh
kubectl -n mta get svc,endpoints,endpointslice,ingress
curl -fsS https://mta.example.org/api/health
```

Il polling web di AI Arranger riprova dopo guasti transitori HTTP e mostra
`N/A` per CPU/GPU quando mancano dati di metering verificabili. Non convertire
il tempo trascorso in consumo GPU fatturabile.

RPM early: la release RPM include revisione, BUILD_INFO e identificativo
univoco del job CI (run ID e attempt). Retention: 20 versioni per formato e
architettura nei repository; gli asset RPM non più indicizzati vengono eliminati
dopo la verifica degli indici pubblici su GitHub Pages.
