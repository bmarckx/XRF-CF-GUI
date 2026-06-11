# Build the offline, self-contained distributable for the XRF Correction Factor Tool.
#
# Run on a machine WITH internet (PySide6 + PyInstaller installed), from the
# project root (xrf_tool):
#
#     powershell -ExecutionPolicy Bypass -File packaging\build_offline_package.ps1
#
# Produces:  packaging\dist\XRF-CF-Tool\            (frozen app: Python + deps bundled)
#            packaging\XRF-CF-Tool-Offline.zip      (app folder + install.bat + README)
#
# Copy the .zip to the offline machine, unzip anywhere, and run install.bat.

$ErrorActionPreference = "Stop"

# Resolve project root (parent of this script's folder)
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root      = Split-Path -Parent $ScriptDir
Set-Location $Root

Write-Host "== Cleaning previous build ==" -ForegroundColor Cyan
Remove-Item -Recurse -Force "$ScriptDir\build", "$ScriptDir\dist" -ErrorAction SilentlyContinue

Write-Host "== Running PyInstaller ==" -ForegroundColor Cyan
pyinstaller "packaging\XRF-CF-Tool.spec" --noconfirm `
    --distpath "packaging\dist" --workpath "packaging\build"
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed." }

$AppDir = "packaging\dist\XRF-CF-Tool"
if (-not (Test-Path "$AppDir\XRF-CF-Tool.exe")) { throw "Build output missing." }

Write-Host "== Assembling distributable ==" -ForegroundColor Cyan
$Stage = "packaging\stage\XRF-CF-Tool-Offline"
Remove-Item -Recurse -Force "packaging\stage" -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force "$Stage" | Out-Null

Copy-Item -Recurse "$AppDir" "$Stage\XRF-CF-Tool"
Copy-Item "packaging\install.bat" "$Stage\install.bat"
if (Test-Path "README.md") { Copy-Item "README.md" "$Stage\README.md" }

$Zip = "packaging\XRF-CF-Tool-Offline.zip"
Remove-Item -Force $Zip -ErrorAction SilentlyContinue
Compress-Archive -Path "$Stage\*" -DestinationPath $Zip

$sizeMB = [math]::Round((Get-Item $Zip).Length / 1MB, 1)
Write-Host ""
Write-Host "== Done ==" -ForegroundColor Green
Write-Host "Distributable: $Zip ($sizeMB MB)"
Write-Host "Copy it to the offline PC, unzip, and run install.bat."
