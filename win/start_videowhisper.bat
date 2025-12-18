@echo off
setlocal

set "PORT=5000"
set "EXE=VideoWhisper.exe"

rem ensure working directory is the folder of this script
cd /d "%~dp0" || (
  echo ERROR: failed to change directory to script location.
  pause
  exit /b 1
)

rem optional: use bundled ffmpeg if present
if exist "%~dp0ffmpeg\ffmpeg.exe" (
  echo Using bundled ffmpeg in %~dp0ffmpeg
  set "PATH=%~dp0ffmpeg;%PATH%"
  set "FFMPEG_BINARY=%~dp0ffmpeg\ffmpeg.exe"
)

if not exist "%EXE%" (
  echo ERROR: %EXE% not found in %CD%.
  echo Make sure you ran win\build-win.bat and are running this script from the VideoWhisper-win folder.
  pause
  exit /b 1
)

echo Starting %EXE% ...
start "VideoWhisper" "%EXE%"

echo Waiting a few seconds for server to start...
rem simple delay instead of complex port polling
timeout /t 8 /nobreak

echo Opening browser at http://127.0.0.1:%PORT%
start "" "http://127.0.0.1:%PORT%"

endlocal
exit /b 0
