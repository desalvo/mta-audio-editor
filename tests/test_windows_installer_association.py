from pathlib import Path


def test_windows_maeproj_open_command_uses_inno_embedded_quotes():
    installer = Path("native/windows-installer.iss").read_text(encoding="utf-8")
    assert (
        'Subkey: "Software\\Classes\\MTA.AudioEditor.Project\\shell\\open\\command"'
        in installer
    )
    assert 'ValueData: """{app}\\{#MyAppExeName}"" ""%1"""' in installer
    assert 'ValueData: ""{app}\\{#MyAppExeName}" "%1""' not in installer
