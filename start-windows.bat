@echo off
rem Starts LinguaSI on your computer with Docker: the database, the API, the website and the
rem mobile app preview. Double-click this file. GETTING-STARTED.md explains every step.
cd /d "%~dp0"
setlocal EnableExtensions EnableDelayedExpansion
title LinguaSI

echo.
echo  LinguaSI
echo  ========
echo.

if not exist "docker-compose.yml" goto :not_extracted

rem Docker Desktop installs docker.exe here. Use it even if PATH has not caught up yet.
where docker >nul 2>nul
if errorlevel 1 if exist "%ProgramFiles%\Docker\Docker\resources\bin\docker.exe" set "PATH=%ProgramFiles%\Docker\Docker\resources\bin;%PATH%"
where docker >nul 2>nul
if errorlevel 1 goto :no_docker

docker info >nul 2>nul
if not errorlevel 1 goto :docker_ready
echo Docker Desktop is not running yet. Starting it...
if exist "%ProgramFiles%\Docker\Docker\Docker Desktop.exe" start "" "%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
echo Waiting for Docker to start. This can take a few minutes...
set /a tries=0
:wait_docker
ping -n 4 127.0.0.1 >nul
docker info >nul 2>nul
if not errorlevel 1 goto :docker_ready
set /a tries+=1
if !tries! lss 60 goto :wait_docker
goto :docker_not_running

:docker_ready
docker compose version >nul 2>nul
if errorlevel 1 goto :old_docker
set "compose_major=0"
set "compose_minor=0"
for /f "tokens=1,2 delims=v." %%a in ('docker compose version --short 2^>nul') do (
  set "compose_major=%%a"
  set "compose_minor=%%b"
)
if !compose_major! lss 2 goto :old_docker
if !compose_major! equ 2 if !compose_minor! lss 24 goto :old_docker

rem Ports: 3000, 8000 and 8081 unless .env chooses others.
set "WEB_PORT=3000"
set "API_PORT=8000"
set "MOBILE_PORT=8081"
if exist ".env" (
  for /f "usebackq eol=# tokens=1,* delims== " %%a in (".env") do (
    if /i "%%a"=="WEB_PORT" set "WEB_PORT=%%b"
    if /i "%%a"=="API_PORT" set "API_PORT=%%b"
    if /i "%%a"=="MOBILE_PORT" set "MOBILE_PORT=%%b"
  )
)

rem Containers left over from an earlier start are removed first. Your data is kept.
docker compose down --remove-orphans >nul 2>nul

call :check_port !WEB_PORT! WEB_PORT
if errorlevel 1 goto :fail
call :check_port !API_PORT! API_PORT
if errorlevel 1 goto :fail
call :check_port !MOBILE_PORT! MOBILE_PORT
if errorlevel 1 goto :fail

echo Building and starting LinguaSI. The first start downloads and builds everything,
echo which takes 5-15 minutes. Later starts take about a minute.
echo.
docker compose up --build --detach --wait
if errorlevel 1 goto :start_failed

echo.
echo Preparing the demo learner. The first time takes a minute or two...
docker compose exec -T api python -m app.cli demo --if-missing
if errorlevel 1 echo The demo learner could not be created. You can still create your own account on the website.

echo.
echo  LinguaSI is running.
echo.
echo    Website:             http://localhost:!WEB_PORT!
echo    Mobile app preview:  http://localhost:!MOBILE_PORT!
echo    API documentation:   http://localhost:!API_PORT!/docs
echo.
echo    Demo learner:        demo@linguasi.app  /  LinguaSI-demo-2026
echo    (or click "Create an account" on the website)
echo.
echo    To stop LinguaSI, double-click stop-windows.bat. Your data is kept.
echo.
start "" "http://localhost:!WEB_PORT!"
echo The website is opening in your browser. You can close this window.
echo.
pause
exit /b 0

:check_port
rem Exit code 1 from PowerShell means something already listens on the port.
powershell -NoProfile -NonInteractive -Command "if (Get-NetTCPConnection -State Listen -LocalPort %1 -ErrorAction SilentlyContinue) { exit 1 }" >nul 2>nul
if errorlevel 2 exit /b 0
if not errorlevel 1 exit /b 0
set /a suggested=%1+1
echo.
echo PROBLEM: port %1 is already used by another program.
echo Close that program, or choose another port: create a file named .env in this
echo folder with the line  %2=!suggested!  and double-click start-windows.bat again.
exit /b 1

:start_failed
echo.
echo Recent messages from LinguaSI:
docker compose logs --tail 40
echo.
echo PROBLEM: LinguaSI did not start. Read the messages above, then see
echo GETTING-STARTED.md, section "If something goes wrong".
goto :fail

:not_extracted
echo PROBLEM: start-windows.bat must run inside the LinguaSI folder.
echo If you downloaded a ZIP file, right-click it, choose "Extract All...", open the
echo extracted folder and double-click start-windows.bat there.
goto :fail

:no_docker
echo PROBLEM: Docker Desktop is not installed.
echo Install it from https://www.docker.com/products/docker-desktop/
echo then open Docker Desktop once and double-click start-windows.bat again.
goto :fail

:docker_not_running
echo PROBLEM: Docker Desktop is not running.
echo Open Docker Desktop from the Start menu and wait until it says "Engine running",
echo then double-click start-windows.bat again. If Docker Desktop shows an error about
echo WSL or virtualization, see GETTING-STARTED.md.
goto :fail

:old_docker
echo PROBLEM: this version of Docker Desktop is too old for LinguaSI.
echo Update it: in Docker Desktop click the gear icon, then "Software updates",
echo or install the latest version from https://www.docker.com/products/docker-desktop/
goto :fail

:fail
echo.
echo More help: GETTING-STARTED.md, section "If something goes wrong".
echo.
pause
exit /b 1
