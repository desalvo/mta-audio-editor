from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from .models import RightsRecord


@dataclass(frozen=True)
class RightsProvider:
    id: str
    name: str
    portal_url: str
    env_search_url: str


PROVIDERS: dict[str, RightsProvider] = {
    "SIAE": RightsProvider(
        id="SIAE",
        name="SIAE",
        portal_url="https://www.siae.it/it/repertorio/",
        env_search_url="MTA_RIGHTS_SIAE_SEARCH_URL",
    ),
    "SOUNDREEF": RightsProvider(
        id="SOUNDREEF",
        name="Soundreef",
        portal_url="https://www.soundreef.com/",
        env_search_url="MTA_RIGHTS_SOUNDREEF_SEARCH_URL",
    ),
}


def provider_catalog() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for provider in PROVIDERS.values():
        endpoint = os.getenv(provider.env_search_url, "").strip()
        out.append({
            "id": provider.id,
            "name": provider.name,
            "portal_url": provider.portal_url,
            "structured_search": bool(endpoint),
            "active_by_default": provider.id in {"SIAE", "SOUNDREEF"},
        })
    return out


def _validated_https(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        raise ValueError("rights provider search endpoint must use HTTPS")
    return url


def _read_json(url: str, params: dict[str, str]) -> Any:
    base = _validated_https(url)
    sep = "&" if "?" in base else "?"
    request_url = f"{base}{sep}{urlencode(params)}"
    req = Request(request_url, headers={"Accept": "application/json", "User-Agent": "MTA-Audio-Editor/rights-search"})  # noqa: S310
    with urlopen(req, timeout=20) as response:  # noqa: S310
        payload = response.read(2_000_000)
    return json.loads(payload.decode("utf-8"))


def _text_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [x.strip() for x in value.replace(";", ",").split(",") if x.strip()]
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            if isinstance(item, str) and item.strip():
                out.append(item.strip())
            elif isinstance(item, dict):
                for key in ("name", "full_name", "display_name"):
                    if str(item.get(key) or "").strip():
                        out.append(str(item[key]).strip())
                        break
        return out
    return []


def _identifiers(item: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    nested = item.get("identifiers")
    if isinstance(nested, dict):
        for key, value in nested.items():
            if value is not None and str(value).strip():
                out[str(key).upper()] = str(value).strip()
    for key in ("iswc", "isrc", "ipi", "work_id", "id", "catalogue_id", "catalog_id"):
        value = item.get(key)
        if value is not None and str(value).strip():
            out[key.upper()] = str(value).strip()
    return out


def _normalise_rows(provider: RightsProvider, payload: Any) -> list[RightsRecord]:
    if isinstance(payload, dict):
        rows = payload.get("results") or payload.get("items") or payload.get("works") or payload.get("data") or []
        if isinstance(rows, dict):
            rows = rows.get("results") or rows.get("items") or rows.get("works") or []
    elif isinstance(payload, list):
        rows = payload
    else:
        rows = []
    records: list[RightsRecord] = []
    for index, raw in enumerate(rows[:100]):
        if not isinstance(raw, dict):
            continue
        title = str(raw.get("title") or raw.get("work_title") or raw.get("name") or "").strip()
        original_title = str(raw.get("original_title") or raw.get("originalTitle") or title).strip()
        authors = _text_list(raw.get("authors") or raw.get("writers") or raw.get("composers") or raw.get("creators"))
        performers = _text_list(raw.get("performers") or raw.get("artists") or raw.get("interpreters"))
        publishers = _text_list(raw.get("publishers") or raw.get("editors") or raw.get("publishers_names"))
        identifiers = _identifiers(raw)
        source_url = str(raw.get("url") or raw.get("source_url") or provider.portal_url).strip()
        if not title and not authors and not identifiers:
            continue
        identity = identifiers.get("ISWC") or identifiers.get("WORK_ID") or identifiers.get("ID") or str(index + 1)
        records.append(RightsRecord(
            uid=f"{provider.id}:{identity}"[:160],
            society=provider.id,
            title=title or original_title or "Opera senza titolo",
            original_title=original_title,
            authors=authors,
            performers=performers,
            publishers=publishers,
            identifiers=identifiers,
            source_url=source_url,
        ))
    return records


def search_provider(provider_id: str, *, title: str, original_title: str = "", artist: str = "", authors: list[str] | None = None) -> dict[str, Any]:
    provider = PROVIDERS.get(provider_id.upper())
    if not provider:
        raise ValueError(f"unsupported rights society: {provider_id}")
    endpoint = os.getenv(provider.env_search_url, "").strip()
    if not endpoint:
        return {
            "provider": provider.id,
            "name": provider.name,
            "portal_url": provider.portal_url,
            "mode": "portal",
            "results": [],
            "message": "Nessuna API strutturata pubblica configurata: apri il repertorio ufficiale e, se necessario, registra manualmente il risultato verificato.",
        }
    payload = _read_json(endpoint, {
        "title": title,
        "original_title": original_title,
        "artist": artist,
        "authors": ", ".join(authors or []),
    })
    return {
        "provider": provider.id,
        "name": provider.name,
        "portal_url": provider.portal_url,
        "mode": "api",
        "results": [item.model_dump(mode="json") for item in _normalise_rows(provider, payload)],
        "message": "",
    }
