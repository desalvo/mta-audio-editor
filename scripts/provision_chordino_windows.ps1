param(
  [string]$Destination = "native/runtime/chordino",
  [string]$PrebuiltPlugin = "native/runtime/chordino-prebuilt"
)
$ErrorActionPreference = "Stop"
$dest = Resolve-Path -LiteralPath (New-Item -ItemType Directory -Force -Path $Destination)
$bin = Join-Path $dest "bin"; $vamp = Join-Path $dest "vamp"
New-Item -ItemType Directory -Force -Path $bin,$vamp | Out-Null
$tmp = Join-Path $env:RUNNER_TEMP "mta-chordino"
Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $tmp | Out-Null

# Sonic Annotator: official current 64-bit Windows host.
$release = Invoke-RestMethod "https://api.github.com/repos/sonic-visualiser/sonic-annotator/releases/latest"
$asset = $release.assets | Where-Object { $_.name -match 'win.*64|64.*win' } | Select-Object -First 1
if (-not $asset) { throw "No 64-bit Windows Sonic Annotator asset found" }
$sa = Join-Path $tmp $asset.name
Invoke-WebRequest $asset.browser_download_url -OutFile $sa
& 7z x $sa "-o$tmp\sa" -y | Out-Null
$exe = Get-ChildItem "$tmp\sa" -Recurse -Filter "sonic-annotator.exe" | Select-Object -First 1
if (-not $exe) { throw "sonic-annotator.exe not found in release asset" }
Copy-Item $exe.FullName (Join-Path $bin "sonic-annotator.exe")
Get-ChildItem $exe.Directory.FullName -File -Filter "*.dll" | ForEach-Object { Copy-Item $_.FullName $bin }

# The x64 NNLS-Chroma DLL is cross-compiled reproducibly in the Linux
# chordino-windows-runtime CI job and transferred as an Actions artifact.
if (-not (Test-Path $PrebuiltPlugin)) { throw "Prebuilt Chordino artifact directory not found: $PrebuiltPlugin" }
$dll = Get-ChildItem $PrebuiltPlugin -Recurse -Filter "nnls-chroma.dll" | Select-Object -First 1
if (-not $dll) { throw "nnls-chroma.dll not found in prebuilt CI artifact" }
Copy-Item $dll.FullName $vamp
Get-ChildItem $dll.Directory.FullName -File | Where-Object { $_.Extension -in '.cat','.n3','.ttl','.txt' -or $_.Name -eq 'COPYING' } | ForEach-Object { Copy-Item $_.FullName $vamp }

$env:VAMP_PATH = $vamp
$list = & (Join-Path $bin "sonic-annotator.exe") -l 2>&1 | Out-String
if ($LASTEXITCODE -ne 0 -or $list -notmatch 'nnls-chroma:chordino') { throw "Bundled Chordino self-test failed`n$list" }
"MTA_NATIVE_CHORDINO_BIN_DIR=$bin" | Out-File -FilePath $env:GITHUB_ENV -Encoding utf8 -Append
"MTA_NATIVE_CHORDINO_VAMP_DIR=$vamp" | Out-File -FilePath $env:GITHUB_ENV -Encoding utf8 -Append
Write-Host "Chordino runtime ready in $dest"
