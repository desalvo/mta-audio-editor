"""HTTPS-only urllib helper: reject URL schemes other than HTTPS, including redirects."""
from __future__ import annotations

from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener


class _HTTPSRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _require_https(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _require_https(url: str) -> None:
    parsed = urlsplit(url)
    if parsed.scheme.lower() != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Only HTTPS URLs without embedded credentials are permitted")


def https_urlopen(request: Request | str, *, timeout: float = 30):
    """Open HTTPS only, including every redirect hop (never file:// or HTTP)."""
    url = request.full_url if isinstance(request, Request) else request
    _require_https(url)
    return build_opener(HTTPSHandler(), _HTTPSRedirectHandler()).open(request, timeout=timeout)
