from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from .models import RightsRecord
from .version import APP_RELEASE


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
    req = Request(request_url, headers={"Accept": "application/json", "User-Agent": f"MTA-Audio-Editor/{APP_RELEASE} (https://github.com/desalvo/mta-audio-editor)"})  # noqa: S310
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

MUSICBRAINZ_API = "https://musicbrainz.org/ws/2"


def _mb_artist_credit(value: Any) -> list[str]:
    out: list[str] = []
    for item in value or []:
        if not isinstance(item, dict):
            continue
        artist = item.get("artist") if isinstance(item.get("artist"), dict) else {}
        name = str(item.get("name") or artist.get("name") or "").strip()
        if name and name not in out:
            out.append(name)
    return out


def _musicbrainz_search_rows(query: str, limit: int) -> list[dict[str, Any]]:
    payload = _read_json(f"{MUSICBRAINZ_API}/recording/", {
        "query": query,
        "fmt": "json",
        "limit": str(max(1, min(25, int(limit)))),
    })
    return (payload.get("recordings") or []) if isinstance(payload, dict) else []


def _normalise_mb_search_text(value: str) -> str:
    import re
    text = str(value or "").replace("\u2018", "'").replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"')
    text = re.sub(r"[^\w\s'&+-]", " ", text, flags=re.UNICODE)
    return " ".join(text.split()).strip()


def search_musicbrainz_metadata(*, title: str, artist: str = "", limit: int = 12) -> list[dict[str, Any]]:
    """Search public MusicBrainz recording metadata with graceful fallbacks.

    Artist metadata in projects can contain combined credits (for example
    ``Lady Gaga & Bruno Mars``). MusicBrainz' ``artist:`` field is stricter,
    so a zero-result artist-qualified query must never suppress a perfectly
    valid title match. Queries therefore progress from precise to permissive.
    """
    import time

    clean_title = _normalise_mb_search_text(title)
    clean_artist = _normalise_mb_search_text(artist)
    if not clean_title:
        return []
    safe_title = clean_title.replace('"', '')
    safe_artist = clean_artist.replace('"', '')
    queries: list[str] = []
    if safe_artist:
        queries.append(f'recording:"{safe_title}" AND artist:"{safe_artist}"')
    queries.append(f'recording:"{safe_title}"')
    # Last fallback uses MusicBrainz' general Lucene search, which tolerates
    # punctuation, alternate credits and small title variations much better.
    queries.append(safe_title)

    raw_rows: list[dict[str, Any]] = []
    for index, query in enumerate(dict.fromkeys(queries)):
        if index:
            time.sleep(1.05)
        rows = _musicbrainz_search_rows(query, max(limit, 15))
        if rows:
            raw_rows.extend(row for row in rows if isinstance(row, dict))
            # A title-only result is already broad enough; do not spend another
            # MusicBrainz request unless all precise queries were empty.
            if query == f'recording:"{safe_title}"' or (safe_artist and index == 0):
                break

    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    title_fold = clean_title.casefold()
    artist_fold = clean_artist.casefold()
    for row in raw_rows:
        mbid = str(row.get("id") or "").strip()
        if not mbid or mbid in seen:
            continue
        seen.add(mbid)
        performers = _mb_artist_credit(row.get("artist-credit"))
        row_title = str(row.get("title") or clean_title).strip()
        score = int(row.get("score") or 0)
        if _normalise_mb_search_text(row_title).casefold() == title_fold:
            score += 25
        if artist_fold and any(artist_fold in _normalise_mb_search_text(name).casefold() or _normalise_mb_search_text(name).casefold() in artist_fold for name in performers):
            score += 15
        results.append({
            "provider": "MUSICBRAINZ",
            "mbid": mbid,
            "title": row_title,
            "performers": performers,
            "first_release_date": str(row.get("first-release-date") or ""),
            "isrcs": [str(x) for x in (row.get("isrcs") or []) if str(x).strip()][:8],
            "score": score,
            "disambiguation": str(row.get("disambiguation") or ""),
            "source_url": f"https://musicbrainz.org/recording/{mbid}",
        })
    results.sort(key=lambda item: (-int(item.get("score") or 0), str(item.get("title") or "").casefold()))
    return results[:max(1, min(25, int(limit)))]


def resolve_musicbrainz_metadata(recording_mbid: str) -> dict[str, Any]:
    """Resolve performers and work authors for one selected MusicBrainz recording."""
    import time

    mbid = str(recording_mbid or "").strip()
    if not mbid:
        raise ValueError("MusicBrainz recording id missing")
    recording = _read_json(f"{MUSICBRAINZ_API}/recording/{mbid}", {
        "fmt": "json",
        "inc": "artist-credits+work-rels+isrcs",
    })
    performers = _mb_artist_credit(recording.get("artist-credit") if isinstance(recording, dict) else [])
    works: list[dict[str, Any]] = []
    seen: set[str] = set()
    for rel in (recording.get("relations") or []) if isinstance(recording, dict) else []:
        if not isinstance(rel, dict) or not isinstance(rel.get("work"), dict):
            continue
        work = rel["work"]
        wid = str(work.get("id") or "").strip()
        if wid and wid not in seen:
            seen.add(wid)
            works.append(work)
    authors: list[str] = []
    identifiers: dict[str, str] = {}
    original_title = ""
    # MusicBrainz asks clients to stay at or below one request per second.
    for index, work in enumerate(works[:3]):
        if index or recording:
            time.sleep(1.05)
        wid = str(work.get("id") or "")
        full = _read_json(f"{MUSICBRAINZ_API}/work/{wid}", {"fmt": "json", "inc": "artist-rels"})
        if not original_title:
            original_title = str(full.get("title") or work.get("title") or "").strip()
        iswcs = full.get("iswcs") or []
        if iswcs and "ISWC" not in identifiers:
            identifiers["ISWC"] = str(iswcs[0])
        for rel in full.get("relations") or []:
            if not isinstance(rel, dict) or not isinstance(rel.get("artist"), dict):
                continue
            if str(rel.get("type") or "").lower() not in {"composer", "lyricist", "writer", "librettist"}:
                continue
            name = str(rel["artist"].get("name") or "").strip()
            if name and name not in authors:
                authors.append(name)
    isrcs = recording.get("isrcs") or [] if isinstance(recording, dict) else []
    if isrcs:
        identifiers["ISRC"] = str(isrcs[0])
    identifiers["MUSICBRAINZ_RECORDING"] = mbid
    return {
        "provider": "MUSICBRAINZ",
        "mbid": mbid,
        "title": str(recording.get("title") or "") if isinstance(recording, dict) else "",
        "original_title": original_title,
        "authors": authors,
        "performers": performers,
        "identifiers": identifiers,
        "source_url": f"https://musicbrainz.org/recording/{mbid}",
    }
