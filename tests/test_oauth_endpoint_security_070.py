from pathlib import Path

AUTH=(Path(__file__).resolve().parents[1]/"app/auth.py").read_text()

def test_s310_suppressed_only_on_validated_request_and_open():
    assert "safe_url = _validate_oauth_endpoint(url)" in AUTH
    assert "UrlRequest(safe_url, data=body, headers=request_headers)  # noqa: S310" in AUTH
    assert "urlopen(request, timeout=15) as resp:  # noqa: S310" in AUTH
    assert AUTH.count("# noqa: S310") == 2
