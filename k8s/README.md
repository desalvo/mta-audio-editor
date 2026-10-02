# Kubernetes manifests

The repository ships a Kustomize base split into dedicated manifests:

- `namespace.yaml`
- `pvc.yaml`
- `deployment.yaml`
- `service.yaml`
- `secret.example.yaml` (example only; intentionally not included by Kustomize)

Create the auth Secret before applying the base, or use the standalone wizard.

```bash
kubectl create namespace mta-audio-editor --dry-run=client -o yaml | kubectl apply -f -
kubectl -n mta-audio-editor create secret generic mta-audio-editor-auth \
  --from-literal=username=admin \
  --from-literal=password='CHANGE-ME' \
  --from-literal=email='admin@example.com'
kubectl apply -k k8s/base
```

Ingress examples:

```bash
kubectl apply -k k8s/overlays/nginx
kubectl apply -k k8s/overlays/haproxy
```

## Standalone wizard

```bash
curl -fsSLo mta-k8s-wizard.py \
  https://raw.githubusercontent.com/desalvo/mta-audio-editor/main/scripts/k8s-wizard.py
python3 mta-k8s-wizard.py
```

The wizard is standard-library only, checks GitHub for a newer wizard version at startup, atomically updates its own file when appropriate, and automatically restarts itself after an update. It remembers the last username, admin email, StorageClass, namespace, nodeSelector, ingress/TLS selection and image. The password is also remembered by default in a local config file with mode `0600`; use `--no-save-password` if that is not desired.


## Upload size

Il limite predefinito è **150 MB**. Il wizard imposta lo stesso valore in `MTA_MAX_UPLOAD_MB` e nell'annotazione dell'Ingress selezionato (`nginx.ingress.kubernetes.io/proxy-body-size` oppure `haproxy-ingress.github.io/proxy-body-size`). Per modificarlo:

```bash
python3 mta-k8s-wizard.py --max-upload-mb 300
```

In modalità interattiva il wizard chiede il valore e lo salva tra le opzioni riutilizzabili.

### Upgrade Kubernetes e readiness

Dalla 0.2.0-58 il pod imposta `fsGroup: 10001` e `fsGroupChangePolicy: OnRootMismatch` per rendere scrivibile il PVC all'utente applicativo non-root. La chiave `email` del Secret bootstrap è opzionale a runtime per mantenere compatibili gli upgrade da release precedenti; il wizard continua comunque a richiedere l'email per le nuove installazioni. È inoltre presente una `startupProbe` su `/api/health` prima di readiness e liveness.

Se un pod resta non Ready dopo un upgrade, controllare `kubectl describe pod` per `CreateContainerConfigError`, `permission denied` sul PVC o errori della probe.


## Image pull policy

Il wizard chiede `imagePullPolicy` e accetta `Always`, `IfNotPresent` o `Never`.
In modalità non interattiva usare, ad esempio:

```bash
python3 mta-k8s-wizard.py --image-pull-policy Always
```
