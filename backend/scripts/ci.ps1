# CI script for backend
Write-Host "Running backend CI checks..."

Set-Location $PSScriptRoot\..

Write-Host "`n=== Installing dependencies ===" -ForegroundColor Cyan
python -m pip install -r requirements.txt --quiet

Write-Host "`n=== Running Ruff linter ===" -ForegroundColor Cyan
python -m ruff check app tests
if ($LASTEXITCODE -ne 0) {
    Write-Host "Ruff check failed!" -ForegroundColor Red
    exit 1
}

Write-Host "`n=== Running Ruff formatter check ===" -ForegroundColor Cyan
python -m ruff format --check app tests
if ($LASTEXITCODE -ne 0) {
    Write-Host "Ruff format check failed!" -ForegroundColor Red
    exit 1
}

Write-Host "`n=== Running pytest ===" -ForegroundColor Cyan
python -m pytest tests -v
if ($LASTEXITCODE -ne 0) {
    Write-Host "Tests failed!" -ForegroundColor Red
    exit 1
}

Write-Host "`n=== All checks passed! ===" -ForegroundColor Green
