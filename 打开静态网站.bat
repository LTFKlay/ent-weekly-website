@echo off
setlocal
title ENT Weekly Preview

cd /d "%~dp0"

where node >nul 2>&1
if errorlevel 1 (
  echo Node.js was not found.
  echo Install Node.js and try again.
  pause
  exit /b 1
)

if not exist "%~dp0dist\index.html" (
  echo Static files were not found.
  echo Run npm run build from the web folder first.
  pause
  exit /b 1
)

netstat -ano | findstr /r /c:":4173 .*LISTENING" >nul
if errorlevel 1 (
  start "ENT Weekly Preview" /min cmd.exe /c node "%~dp0preview-server.cjs"
  ping 127.0.0.1 -n 3 >nul
)

start "" "http://127.0.0.1:4173/"
endlocal
