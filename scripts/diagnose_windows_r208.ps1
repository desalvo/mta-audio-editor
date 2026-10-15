$ErrorActionPreference = 'Stop'
$scriptFile = Join-Path $PSScriptRoot 'installed_diagnostics_r208.py'
$pythonCmd = if (Get-Command py -ErrorAction SilentlyContinue) { 'py' } elseif (Get-Command python -ErrorAction SilentlyContinue) { 'python' } else { throw 'Install Python 3 and make it available on PATH (or py launcher)' }
& $pythonCmd $scriptFile --mode windows @args
exit $LASTEXITCODE
