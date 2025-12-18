@echo off
setlocal

rem Switch to repo root (parent of win\)
cd /d "%~dp0.."

set "VENV=.venv\Scripts\python.exe"
set "DIST_DIR=dist\VideoWhisper"
set "OUT_DIR=VideoWhisper-win"

echo [INFO] Using venv: %VENV%

rem Backup original config.yaml (if any)
if exist "config.yaml" (
  echo [INFO] Backup config.yaml -> config.yaml.bak.win
  copy /Y "config.yaml" "config.yaml.bak.win" >nul
)

rem If config.windows.yaml exists, use it as build-time config.yaml
if exist "config.windows.yaml" (
  echo [INFO] Use config.windows.yaml as build-time config.yaml
  copy /Y "config.windows.yaml" "config.yaml" >nul
)

rem Clean old outputs
if exist "%DIST_DIR%" (
  echo [INFO] Remove old %DIST_DIR%
  rmdir /S /Q "%DIST_DIR%"
)
if exist "%OUT_DIR%" (
  echo [INFO] Remove old %OUT_DIR%
  rmdir /S /Q "%OUT_DIR%"
)

rem Run PyInstaller (do NOT bundle historical output/temp)
echo [INFO] Running PyInstaller...
%VENV% -m PyInstaller --name VideoWhisper --clean --noconfirm --runtime-hook "win\\pyi_rth_ffmpeg_path.py" --add-data "app;app" --add-data "web;web" --add-data "config.yaml;." --add-data "config.docker.yaml;." run.py

if errorlevel 1 (
  echo [ERROR] PyInstaller failed.
  goto RESTORE_CONFIG
)

rem Copy dist output -> VideoWhisper-win
if not exist "%DIST_DIR%" (
  echo [ERROR] %DIST_DIR% not found.
  goto RESTORE_CONFIG
)

echo [INFO] Copy dist output to %OUT_DIR%
robocopy "%DIST_DIR%" "%OUT_DIR%" /E >nul

rem Clean _internal\temp to avoid bundling historical tasks
if exist "%OUT_DIR%\_internal\temp" (
  echo [INFO] Clean %OUT_DIR%\_internal\temp
  rmdir /S /Q "%OUT_DIR%\_internal\temp"
  mkdir "%OUT_DIR%\_internal\temp"
)

rem Copy start script
if exist "win\start_videowhisper.bat" (
  echo [INFO] Copy start_videowhisper.bat
  copy /Y "win\start_videowhisper.bat" "%OUT_DIR%\start_videowhisper.bat" >nul
) else (
  echo [WARN] win\start_videowhisper.bat not found.
)

rem Check ffmpeg
if exist "%OUT_DIR%\ffmpeg\ffmpeg.exe" (
  echo [INFO] Found %OUT_DIR%\ffmpeg\ffmpeg.exe
) else (
  echo [WARN] ffmpeg.exe not found under %OUT_DIR%\ffmpeg\
  echo        - Run: powershell -ExecutionPolicy Bypass -File win\embed-ffmpeg.ps1 -TargetDir "%OUT_DIR%\ffmpeg"
)

:RESTORE_CONFIG
rem Restore original config.yaml
if exist "config.yaml.bak.win" (
  echo [INFO] Restore original config.yaml
  move /Y "config.yaml.bak.win" "config.yaml" >nul
)

echo [INFO] Done.
endlocal
pause
