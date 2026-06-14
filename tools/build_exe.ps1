$ErrorActionPreference = "Stop"

$Root = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
$Python = Join-Path $Root ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Project venv Python was not found: $Python"
}

Push-Location $Root
try {
    & $Python "tools\prepare_release_data.py"
    & $Python -m PyInstaller --noconfirm --clean "CryAssistant.spec"
    Write-Host ""
    Write-Host "Done: $Root\dist\CryAssistant\CryAssistant.exe"
}
finally {
    Pop-Location
}
