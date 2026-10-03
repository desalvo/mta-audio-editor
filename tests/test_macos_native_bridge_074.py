from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "app/main.py").read_text(encoding="utf-8")
JS = (ROOT / "app/static/app.js").read_text(encoding="utf-8")

def test_native_csp_allows_pywebview_dynamic_api_factory_only_in_native_mode():
    assert 'script_policy = "script-src \'self\' \'unsafe-inline\'"' in MAIN
    assert "if NATIVE_SINGLE_USER:" in MAIN
    assert 'script_policy += " \'unsafe-eval\'"' in MAIN
    assert 'f"{script_policy}; media-src' in MAIN

def test_web_csp_does_not_enable_unsafe_eval_unconditionally():
    assert '"script-src \'self\' \'unsafe-inline\' \'unsafe-eval\'; media-src' not in MAIN

def test_073_bridge_readiness_guards_are_retained():
    assert "async function waitForNativeApi(timeoutMs=15000)" in JS
    assert "window.addEventListener('pywebviewready',finish,{once:true})" in JS
