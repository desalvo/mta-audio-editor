param([string]$Destination = "native/runtime/chordino")
$ErrorActionPreference = "Stop"
$dest = Resolve-Path -LiteralPath (New-Item -ItemType Directory -Force -Path $Destination)
$bin = Join-Path $dest "bin"; $vamp = Join-Path $dest "vamp"
New-Item -ItemType Directory -Force -Path $bin,$vamp | Out-Null
$tmp = Join-Path $env:RUNNER_TEMP "mta-chordino"
Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue; New-Item -ItemType Directory -Force -Path $tmp | Out-Null

# Sonic Annotator: use the current official GitHub release and choose the 64-bit Windows asset.
$release = Invoke-RestMethod "https://api.github.com/repos/sonic-visualiser/sonic-annotator/releases/latest"
$asset = $release.assets | Where-Object { $_.name -match 'win.*64|64.*win' } | Select-Object -First 1
if (-not $asset) { throw "No 64-bit Windows Sonic Annotator asset found" }
$sa = Join-Path $tmp $asset.name
Invoke-WebRequest $asset.browser_download_url -OutFile $sa
& 7z x $sa "-o$tmp\sa" -y | Out-Null
$exe = Get-ChildItem "$tmp\sa" -Recurse -Filter "sonic-annotator.exe" | Select-Object -First 1
if (-not $exe) { throw "sonic-annotator.exe not found in release asset" }
Copy-Item $exe.FullName (Join-Path $bin "sonic-annotator.exe")
# Copy DLL dependencies living alongside the executable.
Get-ChildItem $exe.Directory.FullName -File -Filter "*.dll" | ForEach-Object { Copy-Item $_.FullName $bin }

# Native x64 NNLS-Chroma build. The repository builds unmodified upstream Chordino source reproducibly.
$nnlsRelease = Invoke-RestMethod "https://api.github.com/repos/jotapemj/nnls-chroma-win64/releases/latest"
$nnlsAsset = $nnlsRelease.assets | Where-Object { $_.name -match '\.zip$' } | Select-Object -First 1
if (-not $nnlsAsset) { throw "No NNLS-Chroma x64 release asset found" }
$zip = Join-Path $tmp $nnlsAsset.name
Invoke-WebRequest $nnlsAsset.browser_download_url -OutFile $zip
& 7z x $zip "-o$tmp\nnls" -y | Out-Null
$dll = Get-ChildItem "$tmp\nnls" -Recurse -Filter "nnls-chroma.dll" | Select-Object -First 1
if (-not $dll) { throw "nnls-chroma.dll not found" }
Copy-Item $dll.FullName $vamp
Get-ChildItem $dll.Directory.FullName -File | Where-Object { $_.Extension -in '.cat','.n3','.ttl','.txt' } | ForEach-Object { Copy-Item $_.FullName $vamp }

$env:VAMP_PATH = $vamp
$list = & (Join-Path $bin "sonic-annotator.exe") -l 2>&1 | Out-String
if ($LASTEXITCODE -ne 0 -or $list -notmatch 'nnls-chroma:chordino') { throw "Bundled Chordino self-test failed" }
"MTA_NATIVE_CHORDINO_BIN_DIR=$bin" | Out-File -FilePath $env:GITHUB_ENV -Encoding utf8 -Append
"MTA_NATIVE_CHORDINO_VAMP_DIR=$vamp" | Out-File -FilePath $env:GITHUB_ENV -Encoding utf8 -Append
Write-Host "Chordino runtime ready in $dest"
