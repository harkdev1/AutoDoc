$ErrorActionPreference = "Stop"

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$entryPoint = Join-Path $repositoryRoot "autodoc\public_gui.py"
$distPath = Join-Path $repositoryRoot "dist"

if (-not (Test-Path $entryPoint)) {
    throw "Public CLI entry point not found: $entryPoint"
}

$pyInstaller = Get-Command pyinstaller -ErrorAction SilentlyContinue
if (-not $pyInstaller) {
    throw "PyInstaller is not installed. Run: python -m pip install -r public_edition\requirements.txt"
}

Push-Location $repositoryRoot
try {
    & $pyInstaller.Source --onefile --noconsole --clean --name AutoDoc-Public $entryPoint
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed with exit code $LASTEXITCODE"
    }
    Write-Host "Built: $distPath\AutoDoc-Public.exe"
} finally {
    Pop-Location
}
