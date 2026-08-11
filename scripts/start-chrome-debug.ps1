# Start Google Chrome (Default profile) with CDP on port 9222 for RailMadad automation.
param(
    [string]$ProfileDirectory = "Default",
    [int]$Port = 9222
)

$ErrorActionPreference = "Stop"

$chrome = "${env:ProgramFiles}\Google\Chrome\Application\chrome.exe"
if (-not (Test-Path $chrome)) {
    Write-Error "Chrome not found at $chrome"
}

$userData = Join-Path $env:LOCALAPPDATA "Google\Chrome\User Data"
if (-not (Test-Path $userData)) {
    Write-Error "Chrome user data not found at $userData"
}

Write-Host "Closing existing Chrome processes..."
Get-Process chrome -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 2

Write-Host "Starting Chrome (profile: $ProfileDirectory, CDP port: $Port)..."
Start-Process -FilePath $chrome -ArgumentList @(
    "--remote-debugging-port=$Port",
    "--remote-debugging-address=127.0.0.1",
    "--user-data-dir=$userData",
    "--profile-directory=$ProfileDirectory"
)

$cdpUrl = "http://127.0.0.1:$Port/json/version"
Write-Host "Waiting for CDP at $cdpUrl ..."
for ($i = 0; $i -lt 20; $i++) {
    Start-Sleep -Milliseconds 500
    try {
        $resp = Invoke-WebRequest -Uri $cdpUrl -TimeoutSec 2 -UseBasicParsing
        if ($resp.StatusCode -eq 200) {
            Write-Host "OK: Chrome CDP is ready."
            Write-Host $resp.Content
            Write-Host ""
            Write-Host "Next: log in to RailMadad in this Chrome window, then click Generate in the app."
            exit 0
        }
    } catch {
        # retry
    }
}

Write-Error "Chrome started but CDP is not reachable on port $Port. Close all Chrome windows and run this script again."
