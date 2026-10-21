from app.model_rights_dossiers import DOSSIERS
from app.model_license_policy import RESTRICTED_MODELS


def test_drumsep_original_and_mdx23c_evidence_kept_separate():
    evidence = DOSSIERS["drumsep-weights"]
    urls = evidence["references"]
    assert any("issues/9" in url for url in urls)
    assert any("weights-drumsep-v1" in url for url in urls)
    assert any("splitzo/drumsep" in url for url in urls)
    assert "converter cannot grant rights" in evidence["note"]
    assert "drumsep-weights" in RESTRICTED_MODELS
