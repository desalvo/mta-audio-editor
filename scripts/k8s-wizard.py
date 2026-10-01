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

WIZARD_VERSION = "0.2.0-29.1"
APP_VERSION = "0.2.0-29"
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


def parse_bool(value: str, *, field: str = "valore") -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "si", "sì", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off", ""}:
        return False
    raise ValueError(f"{field} non valido: {value!r}; usare yes/no")


def prompt_bool(label: str, default: bool = False) -> bool:
    shown = "yes" if default else "no"
    while True:
        value = input(f"{label} [{shown}]: ").strip()
        if not value:
            return default
        try:
            return parse_bool(value, field=label)
        except ValueError as exc:
            print(exc, file=sys.stderr)


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
    image_pull_policy = values.get("image_pull_policy", "IfNotPresent")
    ingress = values.get("ingress", "none")
    host = values.get("ingress_host", "mta-audio-editor.example.com")
    tls_termination = bool(values.get("tls_termination", False))
    tls_secret = str(values.get("tls_secret", "")).strip()
    max_upload_mb = int(values.get("max_upload_mb", 150))

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
        f"  username: {yq(values['admin_username'])}\n  password: {yq(values['admin_password'])}\n  email: {yq(values['admin_email'])}\n"
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
        fsGroup: 10001
        fsGroupChangePolicy: OnRootMismatch
{indent_selector(selector, 6)}      containers:
        - name: mta-audio-editor
          image: {image}
          imagePullPolicy: {image_pull_policy}
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
            - name: MTA_ADMIN_EMAIL
              valueFrom:
                secretKeyRef:
                  name: mta-audio-editor-auth
                  key: email
                  optional: true
            - name: MTA_MAX_UPLOAD_MB
              value: "{max_upload_mb}"
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
          startupProbe:
            httpGet: {{path: /api/health, port: http}}
            periodSeconds: 2
            timeoutSeconds: 2
            failureThreshold: 60
          readinessProbe:
            httpGet: {{path: /api/health, port: http}}
            periodSeconds: 5
            timeoutSeconds: 2
            failureThreshold: 6
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
        if ingress == "nginx":
            annotation = f'    nginx.ingress.kubernetes.io/proxy-body-size: "{max_upload_mb}m"\n'
        else:
            annotation = (
                '    kubernetes.io/ingress.class: haproxy\n'
                f'    haproxy-ingress.github.io/proxy-body-size: "{max_upload_mb}m"\n'
            )
            if tls_termination:
                annotation += '    haproxy-ingress.github.io/ssl-redirect: "true"\n'

        tls_yaml = ""
        if tls_termination:
            tls_yaml = (
                "  tls:\n"
                "    - hosts:\n"
                f"        - {host}\n"
            )
            if tls_secret:
                tls_yaml += f"      secretName: {tls_secret}\n"

        ingress_yaml = f'''apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: mta-audio-editor
  namespace: {ns}
  annotations:
{annotation}spec:
  ingressClassName: {ingress}
{tls_yaml}  rules:
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
    parser.add_argument("--admin-email")
    parser.add_argument("--storage-class")
    parser.add_argument("--namespace")
    parser.add_argument("--node-selector")
    parser.add_argument("--ingress", choices=["none", "nginx", "haproxy"])
    parser.add_argument("--ingress-host")
    tls_group = parser.add_mutually_exclusive_group()
    tls_group.add_argument("--tls-termination", dest="tls_termination", action="store_true")
    tls_group.add_argument("--no-tls-termination", dest="tls_termination", action="store_false")
    parser.set_defaults(tls_termination=None)
    parser.add_argument(
        "--tls-secret",
        default=None,
        help="Secret Kubernetes TLS da usare; stringa vuota = certificato/default TLS dell'Ingress Controller",
    )
    parser.add_argument("--image")
    parser.add_argument(
        "--image-pull-policy",
        choices=["Always", "IfNotPresent", "Never"],
        help="Kubernetes imagePullPolicy (default IfNotPresent)",
    )
    parser.add_argument("--max-upload-mb", type=int, help="Dimensione massima upload in MB (default 150)")
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
        "admin_email": previous.get("admin_email", ""),
        "storage_class": previous.get("storage_class", ""),
        "namespace": previous.get("namespace", "mta-audio-editor"),
        "node_selector": previous.get("node_selector", ""),
        "ingress": previous.get("ingress", "none"),
        "ingress_host": previous.get("ingress_host", "mta-audio-editor.example.com"),
        "tls_termination": bool(previous.get("tls_termination", False)),
        "tls_secret": previous.get("tls_secret", ""),
        "image": previous.get("image", f"desalvo/mta-audio-editor:{APP_VERSION}"),
        "image_pull_policy": previous.get("image_pull_policy", "IfNotPresent"),
        "max_upload_mb": int(previous.get("max_upload_mb", 150)),
    }
    supplied = {
        "admin_username": args.admin_username,
        "admin_password": args.admin_password,
        "admin_email": args.admin_email,
        "storage_class": args.storage_class,
        "namespace": args.namespace,
        "node_selector": args.node_selector,
        "ingress": args.ingress,
        "ingress_host": args.ingress_host,
        "tls_termination": args.tls_termination,
        "tls_secret": args.tls_secret,
        "image": args.image,
        "image_pull_policy": args.image_pull_policy,
        "max_upload_mb": args.max_upload_mb,
    }
    if args.non_interactive:
        values = {key: (supplied[key] if supplied[key] is not None else defaults[key]) for key in defaults}
    else:
        print(f"MTA Kubernetes Manifest Wizard {WIZARD_VERSION}")
        print("Invio accetta il valore mostrato. Il file di configurazione locale usa permessi 0600.")
        ingress_value = args.ingress or prompt("Ingress (none/nginx/haproxy)", defaults["ingress"])
        ingress_host_value = args.ingress_host or prompt("Ingress host", defaults["ingress_host"])
        tls_termination_value = False
        tls_secret_value = ""
        if ingress_value in {"nginx", "haproxy"}:
            tls_termination_value = (
                args.tls_termination
                if args.tls_termination is not None
                else prompt_bool("TLS termination sull'Ingress", defaults["tls_termination"])
            )
            if tls_termination_value:
                if args.tls_secret is not None:
                    tls_secret_value = args.tls_secret
                else:
                    use_specific_tls_secret = prompt_bool(
                        "Usare un Secret TLS specifico",
                        bool(defaults["tls_secret"]),
                    )
                    if use_specific_tls_secret:
                        tls_secret_value = prompt(
                            "Nome del Secret TLS",
                            defaults["tls_secret"],
                        )
                        while not tls_secret_value:
                            print("Il nome del Secret TLS è obbligatorio se si sceglie un Secret specifico.", file=sys.stderr)
                            tls_secret_value = prompt("Nome del Secret TLS")
                    else:
                        tls_secret_value = ""
        values = {
            "admin_username": args.admin_username or prompt("Username amministratore", defaults["admin_username"]),
            "admin_password": args.admin_password or prompt("Password amministratore", defaults["admin_password"], secret=True),
            "admin_email": args.admin_email or prompt("Email amministratore", defaults["admin_email"]),
            "storage_class": args.storage_class if args.storage_class is not None else prompt("StorageClass PVC (vuoto = default cluster)", defaults["storage_class"]),
            "namespace": args.namespace or prompt("Namespace", defaults["namespace"]),
            "node_selector": args.node_selector if args.node_selector is not None else prompt("nodeSelector (key=value,key2=value2; vuoto = nessuno)", defaults["node_selector"]),
            "ingress": ingress_value,
            "ingress_host": ingress_host_value,
            "tls_termination": tls_termination_value,
            "tls_secret": tls_secret_value,
            "image": args.image or prompt("Immagine container", defaults["image"]),
            "image_pull_policy": args.image_pull_policy or prompt(
                "imagePullPolicy (Always/IfNotPresent/Never)",
                defaults["image_pull_policy"],
            ),
            "max_upload_mb": args.max_upload_mb if args.max_upload_mb is not None else int(prompt("Dimensione massima upload (MB)", str(defaults["max_upload_mb"]))),
        }
    if not values["admin_username"] or not values["admin_password"] or not values["admin_email"]:
        parser.error("username, password ed email amministratore sono obbligatori")
    if "@" not in values["admin_email"]:
        parser.error("email amministratore non valida")
    if values["ingress"] not in {"none", "nginx", "haproxy"}:
        parser.error("ingress deve essere none, nginx o haproxy")
    if values["image_pull_policy"] not in {"Always", "IfNotPresent", "Never"}:
        parser.error("imagePullPolicy deve essere Always, IfNotPresent o Never")
    try:
        values["max_upload_mb"] = int(values["max_upload_mb"])
    except (TypeError, ValueError):
        parser.error("max-upload-mb deve essere un numero intero")
    if not 1 <= values["max_upload_mb"] <= 10240:
        parser.error("max-upload-mb deve essere compreso tra 1 e 10240")
    if values["ingress"] == "none":
        values["tls_termination"] = False
        values["tls_secret"] = ""
    elif not values["tls_termination"]:
        values["tls_secret"] = ""
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
