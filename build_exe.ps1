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

# Autotest paczki: QML, ekrany LIVE/KONFIGURACJA, tryb edycji (EXE nie ma konsoli – wynik w JSON).
$Report = Join-Path $env:TEMP "roots_selftest.json"
Remove-Item $Report -ErrorAction SilentlyContinue
Start-Process (Join-Path $Dist "RootsSoundsystem.exe") -ArgumentList "--selftest", "`"$Report`"" -Wait
if (-not (Test-Path $Report)) { throw "Autotest paczki nie zapisał wyniku ($Report)." }
$Selftest = Get-Content $Report -Raw -Encoding UTF8
$Result = $Selftest | ConvertFrom-Json
if (-not $Result.ok) { throw "Autotest paczki nie przeszedł:`n$Selftest" }
$SizeMB = [math]::Round((Get-ChildItem $Dist -Recurse -File | Measure-Object Length -Sum).Sum / 1MB)
Write-Host "Autotest paczki: OK, wersja $($Result.version), rozmiar $SizeMB MB"
Write-Host "Gotowe: $(Join-Path $Dist 'RootsSoundsystem.exe')"
