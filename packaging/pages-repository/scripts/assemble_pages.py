#!/usr/bin/env python3
"""Assemble verified Pages site from GitHub Actions release artifacts, not Git blobs."""
import argparse
import hashlib
import html
import json
import os
from pathlib import Path
import re
import subprocess
import tarfile
import tempfile

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
        tar.extractall(target, filter="data")
    if not (target / f"apt/{channel}/InRelease").is_file():
        raise ValueError(f"APT signed index missing for {channel}")
    if not (target / f"rpm/{channel}/repodata/repomd.xml.asc").is_file():
        raise ValueError(f"RPM signed index missing for {channel}")
    key = target / "mta-archive-key.asc"
    result = subprocess.run(["gpg", "--batch", "--show-keys", "--with-colons", str(key)], capture_output=True, text=True, check=True)
    fingerprints = [line.split(":")[9].upper() for line in result.stdout.splitlines() if line.startswith("fpr:")]
    if FPR not in fingerprints:
        raise ValueError("Public signing fingerprint mismatch")


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
            subprocess.run(["gh", "run", "download", str(data["run_id"]), "-R", SOURCE,
                            "-n", f"signed-mta-pages-{channel}", "-D", tmp], check=True)
            archive = Path(tmp) / "signed-channel.tar.gz"
            if hashlib.sha256(archive.read_bytes()).hexdigest() != data["sha256"]:
                raise ValueError(f"Signed artifact checksum mismatch: {channel}")
            safe_extract(archive, output, channel)
            archive.unlink()
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
