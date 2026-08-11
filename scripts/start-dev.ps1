# Start local development stack in order: backend -> frontend -> Edge CDP.
param(
    [switch]$SkipEdge
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$BackendHealthUrl = "http://127.0.0.1:8000/api/v1/health"
$FrontendUrl = "http://127.0.0.1:5173"

function Test-HttpReady {
    param([string]$Url)
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
        return $response.StatusCode -ge 200 -and $response.StatusCode -lt 400
    } catch {
        return $false
    }
}

function Test-PortListening {
    param([int]$Port)
    return [bool](netstat -ano | Select-String "127.0.0.1:$Port\s")
}

Write-Host "=== Starting RailMadad development stack ==="
Write-Host ""
Write-Host "Step 1: Ensure PostgreSQL (5432) and Redis (6379) are running locally."
Write-Host "        Update backend/.env if your connection URLs differ."
Write-Host ""

Write-Host "Step 2: Backend (http://127.0.0.1:8000)..."

if (Test-HttpReady -Url $BackendHealthUrl) {
    Write-Host "OK: Backend already running."
} else {
    if (Test-PortListening -Port 8000) {
        Write-Error @"
Port 8000 is in use but the backend health check failed at $BackendHealthUrl.

Another process may be blocking the API. Stop duplicate backend instances, then retry:
  netstat -ano | findstr :8000
  taskkill /PID <pid> /F
"@
    }

    Write-Host "Starting backend in a new window..."
    $backendCmd = "cd `"$Root\backend`"; uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
    Start-Process powershell -ArgumentList @("-NoExit", "-Command", $backendCmd)

    $backendReady = & "$Root\scripts\wait-for-service.ps1" -Url $BackendHealthUrl -Name "Backend API" -TimeoutSeconds 180
    if (-not $backendReady) {
        Write-Error "Backend failed to start on http://127.0.0.1:8000"
    }
}

Write-Host ""
Write-Host "Step 3: Frontend (http://127.0.0.1:5173)..."

if (Test-HttpReady -Url $FrontendUrl) {
    Write-Host "OK: Frontend already running."
} else {
    if (Test-PortListening -Port 5173) {
        Write-Error @"
Port 5173 is in use but the frontend is not responding at $FrontendUrl.

Stop the process using port 5173, then run:
  npm run dev
"@
    }

    Write-Host "Starting frontend in a new window..."
    $frontendCmd = "cd `"$Root`"; npm run dev"
    Start-Process powershell -ArgumentList @("-NoExit", "-Command", $frontendCmd)

    $frontendReady = & "$Root\scripts\wait-for-service.ps1" -Url $FrontendUrl -Name "Frontend (Vite)" -TimeoutSeconds 120
    if (-not $frontendReady) {
        Write-Error "Frontend failed to start on http://127.0.0.1:5173"
    }
}

if (-not $SkipEdge) {
    Write-Host ""
    Write-Host "Step 4: Edge CDP (port 9222)..."
    & "$Root\scripts\start-edge.ps1" -SkipServiceChecks
} else {
    Write-Host ""
    Write-Host "Step 4: Skipping Edge startup (SkipEdge)."
}

Write-Host ""
Write-Host "Development stack is ready."
Write-Host "  App:     $FrontendUrl"
Write-Host "  API:     http://127.0.0.1:8000"
Write-Host "  CDP:     http://127.0.0.1:9222/json/version"
Write-Host ""
Write-Host "Log in to RailMadad in the Edge automation window, then generate reports from the app."
