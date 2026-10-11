"""HTTPS transport must not permit local file access or scheme-downgrade redirects."""
from unittest.mock import Mock

import pytest

from app.secure_https import _HTTPSRedirectHandler, https_urlopen


@pytest.mark.parametrize('url', ['file:///etc/passwd', 'http://example.com/file', 'https://user:pass@example.com/'])
def test_non_https_or_embedded_credentials_rejected(url):
    with pytest.raises(ValueError, match='HTTPS'):
        https_urlopen(url)


@pytest.mark.parametrize('target', ['file:///etc/passwd', 'http://example.com/test', 'https://user:pass@example.com/'])
def test_redirect_downgrade_rejected(target):
    handler = _HTTPSRedirectHandler()
    with pytest.raises(ValueError, match='HTTPS'):
        handler.redirect_request(Mock(full_url='https://example.com'), None, 302, 'Found', {}, target)
