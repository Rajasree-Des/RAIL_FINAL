# Start Microsoft Edge with CDP on port 9222 for RailMadad automation.
# Waits for backend (8000) and frontend (5173) before launching Edge.
param(
    [int]$Port = 9222,
    [string]$UserDataDir = "C:\EdgeDebug",
    [string]$EdgeExecutablePath = $env:EDGE_EXECUTABLE_PATH,
    [string]$RailMadadUrl = "https://railmadad.indianrailways.gov.in/madad/final/home.jsp",
    [string]$AppUrl = "http://127.0.0.1:5173",
    [string]$BackendHealthUrl = "http://127.0.0.1:8000/api/v1/health",
    [int]$ServiceTimeoutSeconds = 120,
    [switch]$SkipServiceChecks
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$WaitScript = Join-Path $ScriptDir "wait-for-service.ps1"

function Resolve-EdgeExecutable {
    param([string]$ExplicitPath)

    if ($ExplicitPath -and (Test-Path $ExplicitPath)) {
        return $ExplicitPath
    }

    $candidates = @(
        "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
        "${env:ProgramFiles}\Microsoft\Edge\Application\msedge.exe"
    )

    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    Write-Error "Microsoft Edge not found. Install Edge or set EDGE_EXECUTABLE_PATH."
}

function Test-HttpReady {
    param([string]$Url)

    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
        return $response.StatusCode -ge 200 -and $response.StatusCode -lt 400
    } catch {
        return $false
    }
}

function Close-StaleEdgeDebugProcesses {
    param([string]$ProfileDir)
    $escaped = [regex]::Escape($ProfileDir)
    Get-CimInstance Win32_Process -Filter "name='msedge.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -match $escaped } |
        ForEach-Object {
            Write-Host "Closing stale Edge automation process PID $($_.ProcessId)"
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        }
}

function Clear-EdgeSessionRestoreState {
    param([string]$ProfileDir)

    $defaultProfile = Join-Path $ProfileDir "Default"
    if (-not (Test-Path $defaultProfile)) {
        return
    }

    $restoreArtifacts = @(
        (Join-Path $defaultProfile "Current Session"),
        (Join-Path $defaultProfile "Current Tabs"),
        (Join-Path $defaultProfile "Last Session"),
        (Join-Path $defaultProfile "Last Tabs"),
        (Join-Path $defaultProfile "Sessions")
    )

    foreach ($artifact in $restoreArtifacts) {
        if (-not (Test-Path $artifact)) {
            continue
        }

        Write-Host "Removing session restore artifact: $artifact"
        Remove-Item -LiteralPath $artifact -Recurse -Force -ErrorAction SilentlyContinue
    }
}

function Get-CdpPageTabs {
    param([string]$ListUrl)

    try {
        $all = Invoke-RestMethod -Uri $ListUrl -TimeoutSec 3
        return @(
            $all | Where-Object {
                $_.type -eq "page" -and
                $_.url -notlike "edge://*" -and
                $_.url -notlike "chrome://*" -and
                $_.url -notlike "devtools://*"
            }
        )
    } catch {
        return @()
    }
}

function Test-ProjectUrlOpen {
    param([string]$Url)

    return $Url -match "127\.0\.0\.1:5173" -or $Url -match "localhost:5173"
}

function Test-RailMadadHomeUrlOpen {
    param([string]$Url)

    return $Url -match "railmadad\.indianrailways\.gov\.in/madad/final/home\.jsp"
}

function Open-CdpTab {
    param(
        [int]$Port,
        [string]$Url
    )

    $newTabUrl = "http://127.0.0.1:$Port/json/new?$Url"
    Invoke-RestMethod -Uri $newTabUrl -Method Get -TimeoutSec 10 | Out-Null
}

function Ensure-RequiredTabs {
    param(
        [int]$Port,
        [string]$AppUrl,
        [string]$RailMadadUrl
    )

    $listUrl = "http://127.0.0.1:$Port/json/list"
    $tabs = Get-CdpPageTabs -ListUrl $listUrl
    $openUrls = @($tabs | ForEach-Object { $_.url })

    $projectOpen = @($openUrls | Where-Object { Test-ProjectUrlOpen -Url $_ }).Count -gt 0
    $railmadadOpen = @($openUrls | Where-Object { Test-RailMadadHomeUrlOpen -Url $_ }).Count -gt 0

    if (-not $projectOpen) {
        Write-Host "Opening missing project tab: $AppUrl"
        Open-CdpTab -Port $Port -Url $AppUrl
    }

    if (-not $railmadadOpen) {
        Write-Host "Opening missing RailMadad tab: $RailMadadUrl"
        Open-CdpTab -Port $Port -Url $RailMadadUrl
    }
}

function Write-RequiredTabSummary {
    param(
        [int]$Port,
        [string]$AppUrl,
        [string]$RailMadadUrl
    )

    $tabs = Get-CdpPageTabs -ListUrl "http://127.0.0.1:$Port/json/list"
    $openUrls = @($tabs | ForEach-Object { $_.url })

    $projectTabs = @($openUrls | Where-Object { Test-ProjectUrlOpen -Url $_ })
    $railmadadTabs = @($openUrls | Where-Object { Test-RailMadadHomeUrlOpen -Url $_ })

    Write-Host ""
    Write-Host "Required tabs:"
    Write-Host "  Project ($AppUrl): $($projectTabs.Count) open"
    foreach ($url in $projectTabs) {
        Write-Host "    - $url"
    }
    Write-Host "  RailMadad ($RailMadadUrl): $($railmadadTabs.Count) open"
    foreach ($url in $railmadadTabs) {
        Write-Host "    - $url"
    }
    Write-Host "  Other page tabs: $($tabs.Count - $projectTabs.Count - $railmadadTabs.Count)"
}

Write-Host "=== RailMadad Edge automation startup ==="
Write-Host ""

if (-not $SkipServiceChecks) {
    Write-Host "Step 1/3: Checking backend..."
    if (-not (Test-HttpReady -Url $BackendHealthUrl)) {
        Write-Host "Backend not ready yet. Waiting up to ${ServiceTimeoutSeconds}s..."
        $backendReady = & $WaitScript -Url $BackendHealthUrl -Name "Backend API" -TimeoutSeconds $ServiceTimeoutSeconds
        if (-not $backendReady) {
            Write-Error @"
Backend API is unavailable at $BackendHealthUrl.

Ensure PostgreSQL and Redis are running locally (see backend/.env), then start the backend:
  cd backend
  uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
"@
        }
    } else {
        Write-Host "OK: Backend API is ready at $BackendHealthUrl"
    }

    Write-Host ""
    Write-Host "Step 2/3: Checking frontend..."
    if (-not (Test-HttpReady -Url $AppUrl)) {
        Write-Host "Frontend not ready yet. Waiting up to ${ServiceTimeoutSeconds}s..."
        $frontendReady = & $WaitScript -Url $AppUrl -Name "Frontend (Vite)" -TimeoutSeconds $ServiceTimeoutSeconds
        if (-not $frontendReady) {
            Write-Error @"
Frontend is unavailable at $AppUrl.

Start the frontend first:
  npm run dev

Vite is configured with strictPort on 5173 — it will not silently switch to another port.
"@
        }
    } else {
        Write-Host "OK: Frontend is ready at $AppUrl"
    }
} else {
    Write-Host "Skipping backend/frontend checks (SkipServiceChecks)."
}

Write-Host ""
Write-Host "Step 3/3: Starting Microsoft Edge with CDP..."

$edge = Resolve-EdgeExecutable -ExplicitPath $EdgeExecutablePath
Write-Host "Using Edge executable: $edge"

if (-not (Test-Path $UserDataDir)) {
    Write-Host "Creating Edge user data directory: $UserDataDir"
    New-Item -ItemType Directory -Path $UserDataDir -Force | Out-Null
}

$cdpVersionUrl = "http://127.0.0.1:$Port/json/version"
$cdpListUrl = "http://127.0.0.1:$Port/json/list"

if (Test-HttpReady -Url $cdpVersionUrl) {
    Write-Host "OK: Edge CDP is already ready on port $Port."
    try {
        $probe = Invoke-WebRequest -Uri $cdpVersionUrl -UseBasicParsing -TimeoutSec 3
        Write-Host $probe.Content
    } catch {
        Write-Host "CDP is ready but could not fetch version details."
    }

    Ensure-RequiredTabs -Port $Port -AppUrl $AppUrl -RailMadadUrl $RailMadadUrl
    Write-RequiredTabSummary -Port $Port -AppUrl $AppUrl -RailMadadUrl $RailMadadUrl
    Write-Host ""
    Write-Host "Next: log in to RailMadad in this Edge window, then click Generate in the app at $AppUrl"
    exit 0
}

Close-StaleEdgeDebugProcesses -ProfileDir $UserDataDir
Start-Sleep -Seconds 2
Clear-EdgeSessionRestoreState -ProfileDir $UserDataDir

Write-Host "Launching Edge (user-data-dir: $UserDataDir, CDP port: $Port)..."
Start-Process -FilePath $edge -ArgumentList @(
    "--remote-debugging-port=$Port",
    "--remote-debugging-address=127.0.0.1",
    "--user-data-dir=$UserDataDir",
    "--disable-restore-session-state",
    "--no-first-run",
    "--no-default-browser-check",
    $AppUrl,
    $RailMadadUrl
)

Write-Host "Waiting for CDP at $cdpVersionUrl ..."
for ($i = 0; $i -lt 40; $i++) {
    Start-Sleep -Milliseconds 500
    if (Test-HttpReady -Url $cdpVersionUrl) {
        try {
            $resp = Invoke-WebRequest -Uri $cdpVersionUrl -UseBasicParsing -TimeoutSec 3
            Write-Host "OK: Edge CDP is ready."
            Write-Host $resp.Content
            Write-RequiredTabSummary -Port $Port -AppUrl $AppUrl -RailMadadUrl $RailMadadUrl
        } catch {
            Write-Host "OK: Edge CDP is ready (could not fetch tab summary)."
        }
        Write-Host ""
        Write-Host "Service summary:"
        Write-Host "  Backend:  $BackendHealthUrl"
        Write-Host "  Frontend: $AppUrl"
        Write-Host "  CDP:      $cdpVersionUrl"
        Write-Host ""
        Write-Host "Next: log in to RailMadad in this Edge window, then click Generate in the app."
        exit 0
    }
}

Write-Error @"
Edge started but CDP is not reachable on port $Port.

Close the Edge debug window and run this script again:
  .\scripts\start-edge.ps1
"@
