# Runs start-windows.bat and stop-windows.bat against a stand-in docker.exe (no Docker needed) and
# checks what they do: a normal start, ports from .env, a busy port, old and new Compose versions, a
# failed start, a folder without docker-compose.yml and a folder name with spaces and brackets.
# Run with Windows PowerShell on Windows.
$ErrorActionPreference = "Stop"
$root = (Resolve-Path "$PSScriptRoot\..\..").Path
$work = Join-Path ([IO.Path]::GetTempPath()) ("linguasi-start-test-" + [Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory "$work\bin" | Out-Null

$csc = Join-Path $env:WINDIR "Microsoft.NET\Framework64\v4.0.30319\csc.exe"
& $csc /nologo "/out:$work\bin\docker.exe" "$PSScriptRoot\FakeDocker.cs"
if ($LASTEXITCODE -ne 0) { throw "Could not compile the docker stand-in" }

$env:PATH = "$work\bin;$env:PATH"
$env:FAKE_DOCKER_LOG = "$work\docker.log"
$stdin = "$work\stdin.txt"
Set-Content -Path $stdin -Value ""  # an empty line answers "pause"
$script:failures = 0

function Fail([string]$message) {
    Write-Host "FAIL: $message"
    $script:failures++
}

# A fresh folder holding the scripts, as if just downloaded.
function New-Scenario([string]$name, [string]$folder = $name) {
    $script:dir = Join-Path $work $folder
    New-Item -ItemType Directory $script:dir | Out-Null
    Copy-Item "$root\start-windows.bat", "$root\stop-windows.bat", "$root\docker-compose.yml" $script:dir
    Set-Content -Path $env:FAKE_DOCKER_LOG -Value $null
    Write-Host "--- $name"
}

function Invoke-Bat([string]$name) {
    $process = Start-Process -FilePath "cmd.exe" -ArgumentList "/d", "/c", $name -WorkingDirectory $script:dir `
        -RedirectStandardInput $stdin -RedirectStandardOutput "$work\out.txt" -RedirectStandardError "$work\err.txt" `
        -NoNewWindow -Wait -PassThru
    $script:code = $process.ExitCode
    $script:out = "$(Get-Content -Raw "$work\out.txt")$(Get-Content -Raw "$work\err.txt")"
}

# The last run exited with $code and printed $text.
function Expect([int]$code, [string]$text) {
    if ($script:code -ne $code) { Fail "exit code $($script:code), expected $code" }
    if (-not $script:out.Contains($text)) {
        Fail "the output does not contain: $text"
        Write-Host ($script:out -replace "(?m)^", "    | ")
    }
}

function Get-Calls { @(Get-Content $env:FAKE_DOCKER_LOG | Where-Object { $_ }) }

function Assert-Called([string]$call) {
    if ((Get-Calls) -notcontains $call) {
        Fail "docker was not called with: $call"
        Get-Calls | ForEach-Object { Write-Host "    > $_" }
    }
}

function Assert-NotCalled([string]$pattern) {
    if (Get-Calls | Where-Object { $_ -like $pattern }) { Fail "docker was called with: $pattern" }
}

Write-Host "--- line endings"
$bat = [IO.File]::ReadAllText("$root\start-windows.bat")
if (-not $bat.Contains("`r`n") -or $bat -match "[^`r]`n") { Fail "start-windows.bat must have CRLF line endings" }
foreach ($file in "start.sh", "docker-compose.yml", "backend\Dockerfile") {
    if ([IO.File]::ReadAllText("$root\$file").Contains("`r")) { Fail "$file must keep LF line endings on Windows" }
}

New-Scenario "normal-start"
Invoke-Bat "start-windows.bat"
Expect 0 "LinguaSI is running."
Expect 0 "Website:             http://localhost:3000"
Expect 0 "Mobile app preview:  http://localhost:8081"
Expect 0 "API documentation:   http://localhost:8000/docs"
Assert-Called "compose down --remove-orphans"
Assert-Called "compose up --build --detach --wait"
Assert-Called "compose exec -T api python -m app.cli demo --if-missing"

New-Scenario "folder-with-spaces" "My LinguaSI (copy)"
Invoke-Bat "start-windows.bat"
Expect 0 "LinguaSI is running."

New-Scenario "ports-from-env"
Set-Content -Path "$script:dir\.env" -Value "# my settings", "WEB_PORT=3101", "API_PORT = 8101", "MOBILE_PORT=8181", "AI_PROVIDER=mock"
Invoke-Bat "start-windows.bat"
Expect 0 "Website:             http://localhost:3101"
Expect 0 "API documentation:   http://localhost:8101/docs"
Expect 0 "Mobile app preview:  http://localhost:8181"

New-Scenario "busy-port"
$listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 3000)
$listener.Start()
try { Invoke-Bat "start-windows.bat" } finally { $listener.Stop() }
Expect 1 "PROBLEM: port 3000 is already used by another program."
Expect 1 "with the line  WEB_PORT=3001"
Assert-NotCalled "compose up*"

New-Scenario "old-compose"
$env:FAKE_COMPOSE_VERSION = "2.20.3"
Invoke-Bat "start-windows.bat"
Remove-Item Env:FAKE_COMPOSE_VERSION
Expect 1 "PROBLEM: this version of Docker Desktop is too old"
Assert-NotCalled "compose up*"

New-Scenario "newer-compose"
$env:FAKE_COMPOSE_VERSION = "v5.0.1-desktop.1"
Invoke-Bat "start-windows.bat"
Remove-Item Env:FAKE_COMPOSE_VERSION
Expect 0 "LinguaSI is running."

New-Scenario "start-fails"
$env:FAKE_UP_EXIT = "1"
Invoke-Bat "start-windows.bat"
Remove-Item Env:FAKE_UP_EXIT
Expect 1 "PROBLEM: LinguaSI did not start."
Assert-Called "compose logs --tail 40"
Assert-NotCalled "compose exec*"

New-Scenario "no-compose-file"
Remove-Item "$script:dir\docker-compose.yml"
Invoke-Bat "start-windows.bat"
Expect 1 "PROBLEM: start-windows.bat must run inside the LinguaSI folder."
Assert-NotCalled "compose*"

New-Scenario "stop"
Invoke-Bat "stop-windows.bat"
Expect 0 "LinguaSI is stopped. Your data is kept."
Assert-Called "compose down"

Remove-Item -Recurse -Force $work -ErrorAction SilentlyContinue
if ($script:failures -gt 0) {
    Write-Host "$($script:failures) check(s) failed."
    exit 1
}
Write-Host "All start-windows.bat and stop-windows.bat checks passed."
