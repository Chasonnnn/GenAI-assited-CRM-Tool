param(
    [string]$VenvPath = ".venv"
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$apiRoot = Split-Path -Parent $scriptDir
Set-Location $apiRoot

$python = Join-Path $VenvPath "Scripts\\python.exe"
if (!(Test-Path $python)) {
    throw "Python not found at $python. Create the venv first."
}

if (Test-Path "requirements-dev.txt") {
    & $python -m pip install -r requirements-dev.txt --use-deprecated=legacy-resolver
}

& $python -m piptools compile --output-file requirements.lock -c constraints.txt requirements.txt
& $python -m piptools compile --output-file test-requirements.lock -c constraints.txt requirements.txt test-requirements.txt
