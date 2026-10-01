#!/usr/bin/env python3
"""MTA Kubernetes Manifest Wizard - standalone, self-updating manifest generator."""
from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import stat
import sys
import tempfile
import urllib.request
from pathlib import Path

WIZARD_VERSION = "0.2.0-18.1"
APP_VERSION = "0.2.0-18"
RAW_URL = "https://raw.githubusercontent.com/desalvo/mta-audio-editor/main/scripts/k8s-wizard.py"
DEFAULT_CONFIG = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "mta-audio-editor" / "k8s-wizard.json"


def version_tuple(value: str) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", value))


def remote_version(data: bytes) -> str | None:
    match = re.search(rb'^WIZARD_VERSION\s*=\s*["\']([^"\']+)["\']', data, re.M)
    return match.group(1).decode() if match else None


def self_update(skip: bool) -> None:
    if skip or os.environ.get("MTA_K8S_WIZARD_NO_UPDATE") == "1":
        return
    script = Path(__file__).resolve()
    if not script.is_file() or not os.access(script, os.W_OK):
        return
    try:
        req = urllib.request.Request(RAW_URL, headers={"User-Agent": "mta-audio-editor-k8s-wizard"})
        with urllib.request.urlopen(req, timeout=5) as response:  # noqa: S310 -- RAW_URL is a hard-coded HTTPS GitHub URL
            data = response.read()
        rv = remote_version(data)
        if not rv or version_tuple(rv) <= version_tuple(WIZARD_VERSION):
            return
        if b"MTA Kubernetes Manifest Wizard" not in data:
            return
        mode = stat.S_IMODE(script.stat().st_mode)
        with tempfile.NamedTemporaryFile("wb", delete=False, dir=script.parent) as tmp:
            tmp.write(data)
            tmp_path = Path(tmp.name)
        os.chmod(tmp_path, mode)
        os.replace(tmp_path, script)
        print(f"Wizard aggiornato automaticamente: {WIZARD_VERSION} -> {rv}. Riavvio...", file=sys.stderr)
        os.execv(  # noqa: S606 -- deliberate self-restart without a shell after atomic update
            sys.executable, [sys.executable, str(script), *sys.argv[1:], "--skip-self-update"]
        )
    except Exception as exc:  # update failure must never block manifest generation
        print(f"Nota: controllo aggiornamenti non riuscito ({exc}). Continuo con la versione locale.", file=sys.stderr)


def load_config(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_config(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(path, 0o600)


def prompt(label: str, default: str = "", secret: bool = False) -> str:
    suffix = ""
    if secret and default:
        suffix = " [salvata; Invio per riutilizzarla]"
    elif default:
        suffix = f" [{default}]"
    fn = getpass.getpass if secret else input
    value = fn(f"{label}{suffix}: ").strip()
    return value or default


def parse_node_selector(value: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for token in [x.strip() for x in value.split(",") if x.strip()]:
        if "=" not in token:
            raise ValueError(f"nodeSelector non valido: {token!r}; usare key=value,key2=value2")
        key, val = token.split("=", 1)
        key, val = key.strip(), val.strip()
        if not key or not val:
            raise ValueError(f"nodeSelector non valido: {token!r}")
        result[key] = val
    return result


def yq(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def indent_selector(selector: dict[str, str], spaces: int = 6) -> str:
    if not selector:
        return ""
    pad = " " * spaces
    lines = [f"{pad}nodeSelector:"]
    for key, value in selector.items():
        lines.append(f"{pad}  {key}: {yq(value)}")
    return "\n".join(lines) + "\n"


def write_manifests(out: Path, values: dict) -> None:
    out.mkdir(parents=True, exist_ok=True)
    ns = values["namespace"]
    storage = values["storage_class"]
    selector = parse_node_selector(values["node_selector"])
    image = values.get("image", f"desalvo/mta-audio-editor:{APP_VERSION}")
    ingress = values.get("ingress", "none")
    host = values.get("ingress_host", "mta-audio-editor.example.com")

    (out / "namespace.yaml").write_text(f"apiVersion: v1\nkind: Namespace\nmetadata:\n  name: {ns}\n")
    sc_line = f"  storageClassName: {yq(storage)}\n" if storage else ""
    (out / "pvc.yaml").write_text(
        "apiVersion: v1\nkind: PersistentVolumeClaim\nmetadata:\n"
        f"  name: mta-audio-editor-data\n  namespace: {ns}\nspec:\n"
        "  accessModes: [\"ReadWriteOnce\"]\n  resources:\n    requests:\n      storage: 20Gi\n" + sc_line
    )
    secret = (
        "apiVersion: v1\nkind: Secret\nmetadata:\n"
        f"  name: mta-audio-editor-auth\n  namespace: {ns}\ntype: Opaque\nstringData:\n"
        f"  username: {yq(values['admin_username'])}\n  password: {yq(values['admin_password'])}\n"
    )
    (out / "secret.yaml").write_text(secret)
    os.chmod(out / "secret.yaml", 0o600)

    deployment = f'''apiVersion: apps/v1
kind: Deployment
metadata:
  name: mta-audio-editor
  namespace: {ns}
spec:
  replicas: 1
  strategy:
    type: Recreate
  selector:
    matchLabels:
      app: mta-audio-editor
  template:
    metadata:
      labels:
        app: mta-audio-editor
    spec:
      automountServiceAccountToken: false
      securityContext:
        seccompProfile:
          type: RuntimeDefault
{indent_selector(selector, 6)}      containers:
        - name: mta-audio-editor
          image: {image}
          imagePullPolicy: IfNotPresent
          ports:
            - containerPort: 8080
              name: http
          env:
            - name: MTA_ADMIN_USERNAME
              valueFrom:
                secretKeyRef:
                  name: mta-audio-editor-auth
                  key: username
            - name: MTA_ADMIN_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: mta-audio-editor-auth
                  key: password
            - name: MTA_MAX_UPLOAD_MB
              value: "512"
          resources:
            requests: {{cpu: 250m, memory: 1Gi}}
            limits: {{cpu: "4", memory: 8Gi}}
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            runAsNonRoot: true
            runAsUser: 10001
            runAsGroup: 10001
            capabilities:
              drop: ["ALL"]
          volumeMounts:
            - {{name: data, mountPath: /data/projects}}
            - {{name: tmp, mountPath: /tmp}}
          readinessProbe:
            httpGet: {{path: /api/health, port: http}}
            initialDelaySeconds: 3
            periodSeconds: 10
          livenessProbe:
            httpGet: {{path: /api/health, port: http}}
            initialDelaySeconds: 10
            periodSeconds: 30
      volumes:
        - name: data
          persistentVolumeClaim:
            claimName: mta-audio-editor-data
        - name: tmp
          emptyDir: {{sizeLimit: 512Mi}}
'''
    (out / "deployment.yaml").write_text(deployment)
    (out / "service.yaml").write_text(f'''apiVersion: v1
kind: Service
metadata:
  name: mta-audio-editor
  namespace: {ns}
spec:
  selector:
    app: mta-audio-editor
  ports:
    - name: http
      port: 80
      targetPort: http
  type: ClusterIP
''')
    resources = ["namespace.yaml", "pvc.yaml", "secret.yaml", "deployment.yaml", "service.yaml"]
    if ingress in {"nginx", "haproxy"}:
        annotation = (
            '    nginx.ingress.kubernetes.io/proxy-body-size: "512m"\n'
            if ingress == "nginx"
            else (
                '    kubernetes.io/ingress.class: haproxy\n'
                '    haproxy-ingress.github.io/proxy-body-size: "512m"\n'
            )
        )
        ingress_yaml = f'''apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: mta-audio-editor
  namespace: {ns}
  annotations:
{annotation}spec:
  ingressClassName: {ingress}
  rules:
    - host: {host}
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: mta-audio-editor
                port:
                  number: 80
'''
        (out / "ingress.yaml").write_text(ingress_yaml)
        resources.append("ingress.yaml")
    (out / "kustomization.yaml").write_text(
        "apiVersion: kustomize.config.k8s.io/v1beta1\nkind: Kustomization\nresources:\n"
        + "".join(f"  - {item}\n" for item in resources)
    )
    (out / "README.txt").write_text(
        "Generated by MTA Kubernetes Manifest Wizard.\n"
        "Review secret.yaml and keep it out of source control.\n"
        f"Apply with: kubectl apply -k {out}\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="MTA Audio Editor Kubernetes manifest wizard")
    parser.add_argument("--admin-username")
    parser.add_argument("--admin-password")
    parser.add_argument("--storage-class")
    parser.add_argument("--namespace")
    parser.add_argument("--node-selector")
    parser.add_argument("--ingress", choices=["none", "nginx", "haproxy"])
    parser.add_argument("--ingress-host")
    parser.add_argument("--image")
    parser.add_argument("--output-dir", default="mta-audio-editor-k8s")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--no-save", action="store_true")
    parser.add_argument("--no-save-password", action="store_true")
    parser.add_argument("--no-self-update", action="store_true")
    parser.add_argument("--skip-self-update", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--non-interactive", action="store_true")
    args = parser.parse_args()
    self_update(args.no_self_update or args.skip_self_update)

    previous = load_config(args.config)
    defaults = {
        "admin_username": previous.get("admin_username", "admin"),
        "admin_password": previous.get("admin_password", ""),
        "storage_class": previous.get("storage_class", ""),
        "namespace": previous.get("namespace", "mta-audio-editor"),
        "node_selector": previous.get("node_selector", ""),
        "ingress": previous.get("ingress", "none"),
        "ingress_host": previous.get("ingress_host", "mta-audio-editor.example.com"),
        "image": previous.get("image", f"desalvo/mta-audio-editor:{APP_VERSION}"),
    }
    supplied = {
        "admin_username": args.admin_username,
        "admin_password": args.admin_password,
        "storage_class": args.storage_class,
        "namespace": args.namespace,
        "node_selector": args.node_selector,
        "ingress": args.ingress,
        "ingress_host": args.ingress_host,
        "image": args.image,
    }
    if args.non_interactive:
        values = {key: (supplied[key] if supplied[key] is not None else defaults[key]) for key in defaults}
    else:
        print(f"MTA Kubernetes Manifest Wizard {WIZARD_VERSION}")
        print("Invio accetta il valore mostrato. Il file di configurazione locale usa permessi 0600.")
        values = {
            "admin_username": args.admin_username or prompt("Username amministratore", defaults["admin_username"]),
            "admin_password": args.admin_password or prompt("Password amministratore", defaults["admin_password"], secret=True),
            "storage_class": args.storage_class if args.storage_class is not None else prompt("StorageClass PVC (vuoto = default cluster)", defaults["storage_class"]),
            "namespace": args.namespace or prompt("Namespace", defaults["namespace"]),
            "node_selector": args.node_selector if args.node_selector is not None else prompt("nodeSelector (key=value,key2=value2; vuoto = nessuno)", defaults["node_selector"]),
            "ingress": args.ingress or prompt("Ingress (none/nginx/haproxy)", defaults["ingress"]),
            "ingress_host": args.ingress_host or prompt("Ingress host", defaults["ingress_host"]),
            "image": args.image or prompt("Immagine container", defaults["image"]),
        }
    if not values["admin_username"] or not values["admin_password"]:
        parser.error("username e password amministratore sono obbligatori")
    if values["ingress"] not in {"none", "nginx", "haproxy"}:
        parser.error("ingress deve essere none, nginx o haproxy")
    try:
        parse_node_selector(values["node_selector"])
    except ValueError as exc:
        parser.error(str(exc))
    out = Path(args.output_dir).expanduser().resolve()
    write_manifests(out, values)
    if not args.no_save:
        saved = dict(values)
        if args.no_save_password:
            saved.pop("admin_password", None)
        save_config(args.config.expanduser(), saved)
    print(f"Manifest generati in: {out}")
    print(f"Applica con: kubectl apply -k {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
