param(
    [string]$VenvPath = ".venv",
    [switch]$WithTests,
    [switch]$UpdateLocks
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$apiRoot = Split-Path -Parent $scriptDir
Set-Location $apiRoot

if (!(Test-Path $VenvPath)) {
    python -m venv $VenvPath
}

$python = Join-Path $VenvPath "Scripts\\python.exe"
if (!(Test-Path $python)) {
    throw "Python not found at $python. Check your venv path."
}

& $python -m pip install --upgrade pip setuptools wheel

if (Test-Path "requirements.txt") {
    & $python -m pip install -r requirements.txt -c constraints.txt --use-deprecated=legacy-resolver
}

if ($WithTests -and (Test-Path "test-requirements.txt")) {
    & $python -m pip install -r test-requirements.txt -c constraints.txt --use-deprecated=legacy-resolver
}

if (Test-Path "requirements-dev.txt") {
    & $python -m pip install -r requirements-dev.txt --use-deprecated=legacy-resolver
}

if ($UpdateLocks) {
    & "$scriptDir\\lock_deps.ps1" -VenvPath $VenvPath
}
