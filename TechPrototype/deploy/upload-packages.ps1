# Upload papermate packages to a Linux host.
# Usage:
#   $env:SSH_HOST = "10.119.9.119"
#   $env:SSH_USER = "root"
#   powershell -File deploy\upload-packages.ps1
#
# Optional:
#   PACKAGES_DIR  package folder
#   SEED_PATH     seed.json path

$ErrorActionPreference = "Stop"
$TechRoot = Split-Path -Parent $PSScriptRoot
$RepoRoot = Split-Path -Parent $TechRoot
$HostName = if ($env:SSH_HOST) { $env:SSH_HOST } else { "10.119.9.119" }
$User = if ($env:SSH_USER) { $env:SSH_USER } else { "root" }
$RemoteDir = "/tmp/papermate"

$PkgCandidates = New-Object System.Collections.Generic.List[string]
if ($env:PACKAGES_DIR) { [void]$PkgCandidates.Add($env:PACKAGES_DIR) }
[void]$PkgCandidates.Add((Join-Path $RepoRoot "..\ppp\deploy-artifacts\packages"))
[void]$PkgCandidates.Add((Join-Path $RepoRoot "dist\packages"))

$Pkg = $null
foreach ($c in $PkgCandidates) {
  $resolved = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($c)
  if (Test-Path -LiteralPath $resolved) {
    $has = @(Get-ChildItem -Path (Join-Path $resolved "papermate-*.tar.gz") -ErrorAction SilentlyContinue)
    if ($has.Count -gt 0) {
      $Pkg = $resolved
      break
    }
  }
}
if (-not $Pkg) {
  throw "No papermate-*.tar.gz found. Run: python TechPrototype/deploy/pack.py  (or set PACKAGES_DIR)"
}

Write-Host ("Packages: {0}" -f $Pkg)
Write-Host ("Target: {0}@{1}:{2}" -f $User, $HostName, $RemoteDir)
Write-Host "Testing SSH..."
ssh -o ConnectTimeout=8 ("{0}@{1}" -f $User, $HostName) ("mkdir -p {0}; echo SSH_OK" -f $RemoteDir)
if ($LASTEXITCODE -ne 0) {
  throw "SSH failed. Check host/user/password or key auth."
}

Get-ChildItem -Path (Join-Path $Pkg "papermate-*.tar.gz") | ForEach-Object {
  Write-Host ("Uploading {0} ..." -f $_.Name)
  scp $_.FullName ("{0}@{1}:{2}/" -f $User, $HostName, $RemoteDir)
  if ($LASTEXITCODE -ne 0) { throw ("scp failed for {0}" -f $_.Name) }
}

$SeedCandidates = New-Object System.Collections.Generic.List[string]
if ($env:SEED_PATH) { [void]$SeedCandidates.Add($env:SEED_PATH) }
[void]$SeedCandidates.Add((Join-Path $RepoRoot "..\ppp\deploy-artifacts\work\seed.json"))
[void]$SeedCandidates.Add((Join-Path $TechRoot "PaperPipeline\data\seed.json"))
foreach ($s in $SeedCandidates) {
  $sp = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($s)
  if (Test-Path -LiteralPath $sp) {
    Write-Host "Uploading seed.json ..."
    scp $sp ("{0}@{1}:{2}/seed.json" -f $User, $HostName, $RemoteDir)
    break
  }
}

$Script = Join-Path $PSScriptRoot "deploy-on-host.sh"
Write-Host "Uploading deploy-on-host.sh ..."
scp $Script ("{0}@{1}:{2}/deploy-on-host.sh" -f $User, $HostName, $RemoteDir)

Write-Host ""
Write-Host "Upload done. On the server run:"
Write-Host ("  ssh {0}@{1}" -f $User, $HostName)
Write-Host ("  sed -i 's/\r$//' {0}/deploy-on-host.sh" -f $RemoteDir)
Write-Host ("  bash {0}/deploy-on-host.sh" -f $RemoteDir)
Write-Host "  systemctl restart papermate-backend"
Write-Host "See TechPrototype/docs/服务器运维与更新.md"
