$ErrorActionPreference = "Stop"

$Root = Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")
$Spec = Join-Path $Root "installer\CryAssistant.iss"
$Exe = Join-Path $Root "dist\CryAssistant\CryAssistant.exe"

if (-not (Test-Path -LiteralPath $Exe)) {
    throw "Build exe first: tools\build_exe.ps1"
}

$Candidates = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
) | Where-Object { $_ -and (Test-Path -LiteralPath $_) }

$Iscc = $Candidates | Select-Object -First 1
if (-not $Iscc) {
    $Command = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($Command) {
        $Iscc = $Command.Source
    }
}

if (-not $Iscc) {
    throw "ISCC.exe was not found. Install Inno Setup 6 and run this script again."
}

Push-Location $Root
try {
    & $Iscc $Spec
    Write-Host ""
    Write-Host "Done: $Root\dist\installer\CryAssistantSetup.exe"
}
finally {
    Pop-Location
}
