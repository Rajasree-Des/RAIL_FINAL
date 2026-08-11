# Wait until an HTTP endpoint responds successfully.
param(
    [Parameter(Mandatory = $true)]
    [string]$Url,

    [Parameter(Mandatory = $true)]
    [string]$Name,

    [int]$TimeoutSeconds = 120,

    [int]$IntervalMilliseconds = 500
)

$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
$attempt = 0

while ((Get-Date) -lt $deadline) {
    $attempt++
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
        if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 400) {
            Write-Host "OK: $Name is ready at $Url (attempt $attempt)."
            return $true
        }
        Write-Host "Waiting for $Name at $Url (HTTP $($response.StatusCode), attempt $attempt)..."
    } catch {
        Write-Host "Waiting for $Name at $Url (attempt $attempt)..."
    }
    Start-Sleep -Milliseconds $IntervalMilliseconds
}

Write-Error "$Name is unavailable at $Url after ${TimeoutSeconds}s."
return $false
