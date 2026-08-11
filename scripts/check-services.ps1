# Check local dev services and print clear status for each component.
param(
    [string]$BackendHealthUrl = "http://127.0.0.1:8000/api/v1/health",
    [string]$FrontendUrl = "http://127.0.0.1:5173",
    [string]$CdpVersionUrl = "http://127.0.0.1:9222/json/version"
)

$ErrorActionPreference = "Continue"

function Test-Service {
    param(
        [string]$Name,
        [string]$Url
    )

    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
        if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 400) {
            return [PSCustomObject]@{
                Name = $Name
                Url = $Url
                Ok = $true
                Detail = "HTTP $($response.StatusCode)"
            }
        }
        return [PSCustomObject]@{
            Name = $Name
            Url = $Url
            Ok = $false
            Detail = "HTTP $($response.StatusCode)"
        }
    } catch {
        return [PSCustomObject]@{
            Name = $Name
            Url = $Url
            Ok = $false
            Detail = $_.Exception.Message
        }
    }
}

Write-Host "=== RailMadad local service check ==="
Write-Host ""

$results = @(
    (Test-Service -Name "Backend API" -Url $BackendHealthUrl),
    (Test-Service -Name "Frontend (Vite)" -Url $FrontendUrl),
    (Test-Service -Name "Edge CDP" -Url $CdpVersionUrl)
)

foreach ($result in $results) {
    $status = if ($result.Ok) { "OK" } else { "FAIL" }
    Write-Host "[$status] $($result.Name)"
    Write-Host "       $($result.Url)"
    Write-Host "       $($result.Detail)"
    Write-Host ""
}

$failed = $results | Where-Object { -not $_.Ok }
if ($failed.Count -gt 0) {
    Write-Host "Fix unavailable services:"
    foreach ($item in $failed) {
        switch ($item.Name) {
            "Backend API" {
                Write-Host "  Backend: ensure PostgreSQL and Redis are running locally"
                Write-Host "           cd backend; uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
            }
            "Frontend (Vite)" {
                Write-Host "  Frontend: npm run dev"
            }
            "Edge CDP" {
                Write-Host "  Edge CDP: .\scripts\start-edge.ps1"
            }
        }
    }
    exit 1
}

Write-Host "All services are ready."
exit 0
