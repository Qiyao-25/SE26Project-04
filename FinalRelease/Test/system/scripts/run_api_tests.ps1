# Run API system tests against PaperMate and write a junit + markdown summary.
# Usage:
#   $env:PAPERMATE_BASE_URL = "http://10.119.9.119"
#   powershell -File FinalRelease\Test\system\scripts\run_api_tests.ps1

$ErrorActionPreference = "Stop"
$FinalRelease = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
$Root = Split-Path -Parent $FinalRelease
$SystemTest = Join-Path $FinalRelease "Test\system"
$Results = Join-Path $SystemTest "results"
New-Item -ItemType Directory -Force -Path $Results | Out-Null

if (-not $env:PAPERMATE_BASE_URL) { $env:PAPERMATE_BASE_URL = "http://10.119.9.119" }
if (-not $env:PAPERMATE_API_PREFIX) { $env:PAPERMATE_API_PREFIX = "/api" }

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$junit = Join-Path $Results "api-junit-$stamp.xml"
$log = Join-Path $Results "api-run-$stamp.log"

Write-Host ("BASE_URL={0}" -f $env:PAPERMATE_BASE_URL)
Push-Location $SystemTest
try {
  python -m pip install -q pytest httpx openpyxl
  python -m pytest api -q --junitxml=$junit 2>&1 | Tee-Object -FilePath $log
  $code = $LASTEXITCODE
} finally {
  Pop-Location
}

python (Join-Path $PSScriptRoot "write_results_xlsx.py") --junit $junit --stamp $stamp
Write-Host ("Results under {0}" -f $Results)
exit $code
