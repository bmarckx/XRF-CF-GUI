@echo off
REM ============================================================
REM  XRF Correction Factor Tool - offline installer (Windows)
REM  Copies the app into your user profile and makes a desktop
REM  shortcut. No internet or admin rights required.
REM ============================================================
setlocal enabledelayedexpansion

set "APPNAME=XRF-CF-Tool"
set "SRC=%~dp0%APPNAME%"
set "DEST=%LOCALAPPDATA%\Programs\%APPNAME%"

if not exist "%SRC%\%APPNAME%.exe" (
    echo ERROR: Could not find "%SRC%\%APPNAME%.exe".
    echo Make sure this installer sits next to the "%APPNAME%" folder.
    pause
    exit /b 1
)

echo.
echo Installing %APPNAME% to:
echo   %DEST%
echo.

if exist "%DEST%" (
    echo Removing previous installation...
    rmdir /s /q "%DEST%"
)

echo Copying files (this may take a moment)...
xcopy /e /i /q /y "%SRC%" "%DEST%" >nul
if errorlevel 1 (
    echo ERROR: copy failed.
    pause
    exit /b 1
)

echo Creating desktop shortcut...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$d=[Environment]::GetFolderPath('Desktop'); $s=(New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $d 'XRF-CF-Tool.lnk')); $s.TargetPath=(Join-Path '%DEST%' '%APPNAME%.exe'); $s.WorkingDirectory='%DEST%'; $s.Description='XRF Correction Factor Tool'; $s.Save()"

echo.
echo ============================================================
echo  Done. Look for "XRF-CF-Tool" on your desktop.
echo  On first launch you will be asked to pick a default folder
echo  for opening and saving project files.
echo ============================================================
echo.
pause
