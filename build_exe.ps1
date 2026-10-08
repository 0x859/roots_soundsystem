$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$Py = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) {
    throw "Brak $Py — utwórz venv i zainstaluj requirements.txt."
}

Set-Location $Root
& $Py (Join-Path $Root "assets\generate_icon.py")
if ($LASTEXITCODE -ne 0) { throw "Generowanie ikony nie powiodło się." }

& $Py -m pip install -q "pyinstaller>=6.10"
if ($LASTEXITCODE -ne 0) { throw "Instalacja PyInstaller nie powiodła się." }

& $Py -m PyInstaller --noconfirm --clean (Join-Path $Root "RootsSoundsystem.spec")
if ($LASTEXITCODE -ne 0) { throw "PyInstaller zakończył się błędem." }

$Dist = Join-Path $Root "dist\RootsSoundsystem"
Copy-Item (Join-Path $Root "assets\icon.ico") (Join-Path $Dist "icon.ico") -Force
Write-Host "Gotowe: $(Join-Path $Dist 'RootsSoundsystem.exe')"
