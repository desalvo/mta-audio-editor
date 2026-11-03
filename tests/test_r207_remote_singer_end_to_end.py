"""Legacy native singer/SAM routes fail before configuration or transport effects."""
import pytest
from app import native_ai_routing as routing

@pytest.mark.parametrize('kind',['sam-audio','singer-separation'])
def test_removed_remote_separator_never_creates_settings(tmp_path,monkeypatch,kind):
    target=tmp_path/'settings.json'
    monkeypatch.setattr(routing,'_file',lambda:target)
    with pytest.raises(ValueError,match='removed'):routing.configure(kind,'remote','https://example.test','secret')
    with pytest.raises(ValueError,match='removed'):routing.is_remote(kind)
    assert not target.exists()
