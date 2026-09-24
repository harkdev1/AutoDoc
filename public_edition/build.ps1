param(
    [string]$Version = $env:AUTODOC_VERSION
)

$ErrorActionPreference = "Stop"

if (-not $Version) {
    $Version = "0.1.0-public"
}

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
    $env:AUTODOC_VERSION = $Version
    & $pyInstaller.Source --onefile --noconsole --clean --name AutoDoc-Public $entryPoint
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed with exit code $LASTEXITCODE"
    }
    $executablePath = Join-Path $distPath "AutoDoc-Public.exe"
    $checksum = (Get-FileHash -Algorithm SHA256 $executablePath).Hash.ToLowerInvariant()
    Set-Content -Path "$executablePath.sha256" -Value "$checksum  AutoDoc-Public.exe" -Encoding ascii
    Write-Host "Built AutoDoc $Version : $distPath\AutoDoc-Public.exe"
    Write-Host "SHA-256: $checksum"
} finally {
    Pop-Location
}
