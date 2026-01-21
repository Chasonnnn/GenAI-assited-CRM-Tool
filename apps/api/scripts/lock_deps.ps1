param(
    [string]$VenvPath = ".venv"
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$apiRoot = Split-Path -Parent $scriptDir
Set-Location $apiRoot

& uv lock
