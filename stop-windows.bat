@echo off
rem Stops LinguaSI. Your accounts and progress are kept. Start again with start-windows.bat.
setlocal
title LinguaSI
cd /d "%~dp0"
where docker >nul 2>nul
if errorlevel 1 if exist "%ProgramFiles%\Docker\Docker\resources\bin\docker.exe" set "PATH=%ProgramFiles%\Docker\Docker\resources\bin;%PATH%"
docker compose down
echo.
echo LinguaSI is stopped. Your data is kept. Start it again with start-windows.bat.
echo.
pause
