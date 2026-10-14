"""The worker cannot shadow the archive's generated manifest entry."""
import json
import pytest
from app.ai_worker_artifacts import package_artifacts

@pytest.mark.parametrize('name', ['manifest.json', 'Manifest.json', 'MANIFEST.JSON'])
def test_reserved_manifest_alias_rejected_before_packaging(tmp_path, name):
    (tmp_path / name).write_text('{}')
    (tmp_path / 'output.manifest.json').write_text(json.dumps({'version': 1, 'files': [{'name': name, 'type': 'application/json'}]}))
    with pytest.raises(ValueError, match='Unsafe or duplicate'):
        package_artifacts(tmp_path)
