param(
    [string]$VenvPath = ".venv",
    [switch]$WithTests,
    [switch]$UpdateLocks
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$apiRoot = Split-Path -Parent $scriptDir
Set-Location $apiRoot

$env:UV_PROJECT_ENVIRONMENT = $VenvPath

if ($UpdateLocks) {
    & "$scriptDir\\lock_deps.ps1"
}

$syncArgs = @("sync", "--frozen", "--no-install-project")
if ($WithTests) {
    $syncArgs += @("--extra", "test")
}

& uv @syncArgs
