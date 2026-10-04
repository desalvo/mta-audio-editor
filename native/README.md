# Native desktop builds

The Windows and macOS editions run the same editor engine locally, inside a native
`pywebview` window. They are deliberately **single-user**:

- no login page;
- no account administration;
- no registration, SMTP, TOTP or user-management UI;
- no project sharing UI;
- the embedded FastAPI server binds only to `127.0.0.1`;
- project data is stored in the current OS user's application-data directory.

Data locations:

- macOS: `~/Library/Application Support/MTA Audio Editor`
- Windows: `%LOCALAPPDATA%\MTA Audio Editor`

FFmpeg/FFprobe are bundled by the GitHub Actions build. Demucs/PyTorch are bundled
as well; model weights are downloaded on first use and cached under the native
application data directory.

GitHub Actions produces:

- macOS Apple Silicon/ARM64 `.dmg`
- Windows x64 `Setup.exe`

Tag builds additionally upload both installers to the GitHub Release for that tag.

## Native Demucs model management

Windows/macOS desktop builds obtain requested Demucs models from the configured MTA Audio Editor model server. The server publishes native ZIP bundles containing the model YAML and checkpoints. A requested model is installed automatically before splitting; Settings -> **Manage Demucs models** can force an update or delete the local copy. `MTA_MODEL_SERVER_URL` can override the default model server.
