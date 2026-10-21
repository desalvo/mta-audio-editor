#!/usr/bin/env python3
"""Assemble verified Pages site from GitHub Actions release artifacts, not Git blobs."""
import argparse
import hashlib
import html
import json
from pathlib import Path
import re
import subprocess
import tarfile
import tempfile
import time

SOURCE = "desalvo/mta-audio-editor"
FPR = "0833A4FCB008ECAC9F98840B4C1D2DD95F5AEDB7"


def load_manifest(path, channel):
    data = json.loads(path.read_text())
    if (data.get("schema") != 1 or data.get("channel") != channel
            or data.get("repository") != SOURCE
            or not isinstance(data.get("run_id"), int)
            or data["run_id"] < 1
            or not re.fullmatch(r"[a-f0-9]{40}", data.get("commit", ""))
            or not re.fullmatch(r"[a-f0-9]{64}", data.get("sha256", ""))):
        raise ValueError(f"Invalid {channel} manifest")
    if "pages_sha256" in data and not re.fullmatch(r"[a-f0-9]{64}", str(data["pages_sha256"])):
        raise ValueError(f"Invalid {channel} Pages checksum")
    return data


def safe_extract(archive, target, channel):
    allowed = (f"apt/{channel}/", f"rpm/{channel}/")
    with tarfile.open(archive, "r:gz") as tar:
        for entry in tar:
            name = entry.name.removeprefix("./")
            if name in ("", ".", ".nojekyll", "mta-archive-key.asc"):
                pass
            elif not any(name == p[:-1] or name.startswith(p) for p in allowed) and name not in ("apt", "rpm"):
                raise ValueError(f"Unexpected archive entry: {name}")
            if entry.issym() or entry.islnk() or not (entry.isfile() or entry.isdir()):
                raise ValueError(f"Unsafe archive entry: {name}")
            dest = (target / name).resolve()
            if not dest.is_relative_to(target.resolve()):
                raise ValueError(f"Archive path escape: {name}")
        # Signed-channel artifacts intentionally retain all RPM payloads for
        # subsequent repository publication/retention.  Those same payloads
        # are published as GitHub Release assets, NOT GitHub Pages content.
        # Validate every member above, but do not materialize RPM binaries.
        members = [entry for entry in tar.getmembers()
                   if not (entry.name.removeprefix("./").startswith(f"rpm/{channel}/")
                           and entry.name.lower().endswith(".rpm"))]
        tar.extractall(target, members=members, filter="data")
    if list((target / f"rpm/{channel}").rglob("*.rpm")):
        raise ValueError("RPM binaries must not be deployed through GitHub Pages")
    if not (target / f"apt/{channel}/InRelease").is_file():
        raise ValueError(f"APT signed index missing for {channel}")
    for el in ("el9", "el10"):
        if not (target / f"rpm/{channel}/{el}/repodata/repomd.xml.asc").is_file():
            raise ValueError(f"RPM signed index missing for {channel}/{el}")
    key = target / "mta-archive-key.asc"
    result = subprocess.run(["gpg", "--batch", "--show-keys", "--with-colons", str(key)], capture_output=True, text=True, check=True)
    fingerprints = [line.split(":")[9].upper() for line in result.stdout.splitlines() if line.startswith("fpr:")]
    if FPR not in fingerprints:
        raise ValueError("Public signing fingerprint mismatch")


def sha256_file(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def download_artifact(run_id, artifact, destination, *, timeout=1200, heartbeat=30):
    """Bound silent gh downloads and report activity without exposing auth/URLs."""
    print(f"Download {artifact}: source run {run_id}, limit {timeout}s", flush=True)
    started = time.monotonic()
    with subprocess.Popen(["gh", "run", "download", str(run_id), "-R", SOURCE,
                           "-n", artifact, "-D", str(destination)]) as process:
        try:
            while True:
                remaining = timeout - (time.monotonic() - started)
                if remaining <= 0:
                    raise TimeoutError(f"Download {artifact} timed out after {timeout}s; "
                                       "check source Actions token permissions and artifact connectivity")
                try:
                    code = process.wait(timeout=min(heartbeat, remaining))
                    break
                except subprocess.TimeoutExpired:
                    elapsed = int(time.monotonic() - started)
                    print(f"Download {artifact} still active: {elapsed}s elapsed", flush=True)
            if code:
                raise RuntimeError(f"Download {artifact} failed (exit {code}); "
                                   "check token Actions:read permission and artifact retention")
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
    print(f"Download {artifact} completed in {int(time.monotonic() - started)}s", flush=True)


def assemble(manifests, output):
    output.mkdir(parents=True, exist_ok=True)
    any_channel = False
    with tempfile.TemporaryDirectory() as tmp:
        for channel in ("early", "stable"):
            path = manifests / f"{channel}.json"
            if not path.exists():
                continue
            any_channel = True
            data = load_manifest(path, channel)
            pages_only = "pages_sha256" in data
            artifact = f"signed-mta-pages-{'site-' if pages_only else ''}{channel}"
            if not pages_only:
                print(f"Legacy manifest {channel}: full retained package download required; "
                      "republish with Pages-only bundle to reduce download size", flush=True)
            destination = Path(tmp) / channel
            destination.mkdir()
            download_artifact(data["run_id"], artifact, destination)
            archive = destination / ("pages-site.tar.gz" if pages_only else "signed-channel.tar.gz")
            print(f"Verify {channel}: {archive.stat().st_size:,} bytes", flush=True)
            if sha256_file(archive) != data["pages_sha256" if pages_only else "sha256"]:
                raise ValueError(f"Signed artifact checksum mismatch: {channel}")
            print(f"Extract and validate {channel}", flush=True)
            safe_extract(archive, output, channel)
            archive.unlink()
            print(f"Channel {channel} ready", flush=True)
    if not any_channel:
        raise ValueError("No signed channel manifests available")
    (output / ".nojekyll").touch()
    render_file_indexes(output)


def render_file_indexes(output):
    """Publish browsable static listings; never alter signed package indexes."""
    from urllib.parse import quote

    def page(title, heading, items, prefix=""):
        rows = []
        for label, href, size, is_dir in items:
            safe_href = html.escape(quote(href, safe="/._-~"), quote=True)
            rows.append(f"<tr><td><a href=\"{safe_href}\">{html.escape(label)}</a></td>"
                        f"<td>{'Directory' if is_dir else f'{size:,} bytes'}</td></tr>")
        return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
                "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
                f"<title>{html.escape(title)}</title>"
                "<style>body{font:16px system-ui,sans-serif;max-width:1050px;margin:3rem auto;padding:0 1.2rem}"
                "table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid #ddd;padding:.6rem;text-align:left}"
                "a{color:#1561a5}code{overflow-wrap:anywhere}</style></head><body>"
                f"<h1>{html.escape(heading)}</h1><p>Signed APT/DNF artifacts. "
                "Files are provided as-is; verify their signatures with your package manager.</p>"
                "<p><a href=\"/mta-audio-editor-packages/\">Repository home</a></p>"
                "<table><thead><tr><th>Name</th><th>Size / type</th></tr></thead><tbody>"
                + "".join(rows) + "</tbody></table></body></html>\n")

    for directory in sorted([output, *(d for d in output.rglob("*") if d.is_dir())]):
        items = []
        for child in sorted(directory.iterdir(), key=lambda x: (not x.is_dir(), x.name)):
            if child.name == "index.html" or child.name.startswith("."):
                continue
            if child.is_symlink():
                raise ValueError(f"Unexpected symbolic link: {child}")
            if child.is_file() or child.is_dir():
                items.append((child.name + ("/" if child.is_dir() else ""),
                              child.name + ("/" if child.is_dir() else ""),
                              child.stat().st_size if child.is_file() else 0, child.is_dir()))
        relative = directory.relative_to(output).as_posix()
        heading = "MTA Audio Editor Server Packages" if directory == output else f"Files: /{relative}/"
        (directory / "index.html").write_text(page(heading, heading, items), encoding="utf-8")



if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifests", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assemble(args.manifests, args.output)
