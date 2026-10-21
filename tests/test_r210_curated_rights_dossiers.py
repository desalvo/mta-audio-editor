from app.model_rights_dossiers import DOSSIERS
from app import model_license_policy as policy


def test_rights_dossiers_are_non_authorizing():
    assert DOSSIERS['drumsep-weights']['status']=='checkpoint_rights_unconfirmed'
    assert DOSSIERS['chordformer']['status']=='five_checkpoints_unconfirmed'
    assert DOSSIERS['madmom']['status']=='noncommercial_weights'
    assert DOSSIERS['sam-audio']['status']=='published_model_license'
    for name, record in DOSSIERS.items():
        assert record['references'] and all(link.startswith('https://') for link in record['references'])
        assert record['note']


def test_dossiers_do_not_change_admission(tmp_path, monkeypatch):
    monkeypatch.setenv('MTA_DATA_DIR',str(tmp_path))
    for name in ('drumsep-weights','chordformer','madmom','uvr-kara-2'):
        assert name in DOSSIERS
        try:
            policy.evaluate_model(name)
        except policy.LicenseDenied:
            pass
        else:
            raise AssertionError(name+' unexpectedly enabled')
    assert policy.evaluate_model('sam-audio').mode=='cost_recovery'
    rows={row['id']:row for row in policy.catalog()}
    assert rows['drumsep-weights']['rights_dossier']==DOSSIERS['drumsep-weights']
    assert rows['uvr-kara-2']['rights_dossier']==DOSSIERS['uvr-kara-2']
