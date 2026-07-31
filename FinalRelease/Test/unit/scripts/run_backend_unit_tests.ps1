# Run full backend pytest suite and write coverage artifacts under FinalRelease/Test/unit/backend/reports/.
param(
  [switch]$SearchOnly
)

$ErrorActionPreference = "Stop"
$FinalRelease = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
$Root = Split-Path -Parent $FinalRelease
$UnitTest = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $FinalRelease "source\backend"
$Reports = Join-Path $UnitTest "backend\reports"
New-Item -ItemType Directory -Force -Path $Reports | Out-Null

Push-Location $Backend
try {
  python -m pip install -q pytest pytest-cov httpx
  if ($SearchOnly) {
    bash scripts/run_search_coverage.sh
  } else {
    python -m pytest -q --junitxml="$Reports\junit-full.xml" --cov=app --cov-report=xml:"$Reports\coverage-full.xml" --cov-report=html:"$Reports\coverage-html"
  }
  exit $LASTEXITCODE
} finally {
  Pop-Location
}
