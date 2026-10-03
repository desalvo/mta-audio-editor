import pytest

from app.auth import _validate_oauth_endpoint


@pytest.mark.parametrize("url", [
    "https://oauth2.googleapis.com/token",
    "https://openidconnect.googleapis.com/v1/userinfo",
    "https://github.com/login/oauth/access_token",
    "https://api.github.com/user",
    "https://graph.facebook.com/oauth/access_token",
])
def test_oauth_endpoint_accepts_known_https_provider_hosts(url):
    assert _validate_oauth_endpoint(url) == url


@pytest.mark.parametrize("url", [
    "http://api.github.com/user",
    "file:///etc/passwd",
    "https://evil.example/user",
    "https://api.github.com.evil.example/user",
    "https://user:pass@api.github.com/user",
    "https://api.github.com:444/user",
])
def test_oauth_endpoint_rejects_unsafe_urls(url):
    with pytest.raises(ValueError, match="Endpoint OAuth non consentito"):
        _validate_oauth_endpoint(url)
