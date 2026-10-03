from pathlib import Path


def test_server_default_upload_limit_is_one_gib():
    root = Path(__file__).resolve().parents[1]
    text = (root / "app/main.py").read_text(encoding="utf-8")
    assert 'os.getenv("MTA_MAX_UPLOAD_MB", "1024")' in text


def test_container_and_k8s_defaults_are_one_gib():
    root = Path(__file__).resolve().parents[1]
    assert 'MTA_MAX_UPLOAD_MB:-1024' in (root / "docker-compose.yml").read_text(encoding="utf-8")
    assert 'value: "1024"' in (root / "k8s/base/deployment.yaml").read_text(encoding="utf-8")
    assert 'proxy-body-size: "1024m"' in (root / "k8s/overlays/nginx/ingress.yaml").read_text(encoding="utf-8")
    assert 'proxy-body-size: "1024m"' in (root / "k8s/overlays/haproxy/ingress.yaml").read_text(encoding="utf-8")


def test_native_upload_limit_is_user_configurable():
    root = Path(__file__).resolve().parents[1]
    native = (root / "native/mta_audio_editor_native.py").read_text(encoding="utf-8")
    ui = (root / "app/static/app.js").read_text(encoding="utf-8")
    assert 'native-settings.json' in native
    assert 'def get_native_settings' in native
    assert 'def set_native_settings' in native
    assert 'app_main.MAX_UPLOAD_BYTES = value * 1024 * 1024' in native
    assert 'showNativeSettings' in ui and 'saveNativeSettings' in ui
