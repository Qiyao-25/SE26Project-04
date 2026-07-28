# Run full backend pytest suite and write coverage artifacts under UnitTest/backend/reports/.
param(
    [switch]$SearchOnly
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$Backend = Join-Path $Root "TechPrototype\backend"
$Reports = Join-Path $Root "UnitTest\backend\reports"
New-Item -ItemType Directory -Force -Path (Join-Path $Reports "coverage-html") | Out-Null

Push-Location $Backend
$env:PYTHONPATH = $Backend
try {
    python -m pip install -e ".[dev]" -q
    if ($SearchOnly) {
        bash scripts/run_search_coverage.sh
        exit $LASTEXITCODE
    }
    python -m pytest `
        --cov=app `
        --cov-config=.coveragerc `
        --cov-report=term-missing `
        --cov-report=xml:$Reports/coverage.xml `
        --cov-report=html:$Reports/coverage-html `
        --junitxml=$Reports/junit-full.xml
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
