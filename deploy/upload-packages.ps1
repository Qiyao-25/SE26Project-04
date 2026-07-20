# 从本机上传安装包到 Linux 服务器
# 用法：
#   $env:SSH_HOST = "10.119.9.119"
#   $env:SSH_USER = "root"
#   powershell -File deploy\upload-packages.ps1
#
# 可选环境变量：
#   PACKAGES_DIR  安装包目录（默认依次尝试仓库外 ppp 与 dist/packages）
#   SEED_PATH     seed.json 路径

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$HostName = if ($env:SSH_HOST) { $env:SSH_HOST } else { "10.119.9.119" }
$User = if ($env:SSH_USER) { $env:SSH_USER } else { "root" }
$RemoteDir = "/tmp/papermate"

$PkgCandidates = @()
if ($env:PACKAGES_DIR) { $PkgCandidates += $env:PACKAGES_DIR }
$PkgCandidates += (Join-Path $RepoRoot "..\ppp\deploy-artifacts\packages")
$PkgCandidates += (Join-Path $RepoRoot "dist\packages")

$Pkg = $null
foreach ($c in $PkgCandidates) {
  $resolved = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($c)
  if (Test-Path $resolved) {
    $has = Get-ChildItem (Join-Path $resolved "papermate-*.tar.gz") -ErrorAction SilentlyContinue
    if ($has) { $Pkg = $resolved; break }
  }
}
if (-not $Pkg) {
  throw "未找到 papermate-*.tar.gz。请先 python deploy/pack.py，或设置 PACKAGES_DIR。"
}

Write-Host "Packages: $Pkg"
Write-Host "Target ${User}@${HostName}:${RemoteDir}"
Write-Host "Testing SSH..."
ssh -o ConnectTimeout=8 "${User}@${HostName}" "mkdir -p ${RemoteDir} && echo SSH_OK"

Get-ChildItem (Join-Path $Pkg "papermate-*.tar.gz") | ForEach-Object {
  Write-Host "Uploading $($_.Name) ..."
  scp $_.FullName "${User}@${HostName}:${RemoteDir}/"
}

$SeedCandidates = @()
if ($env:SEED_PATH) { $SeedCandidates += $env:SEED_PATH }
$SeedCandidates += (Join-Path $RepoRoot "..\ppp\deploy-artifacts\work\seed.json")
$SeedCandidates += (Join-Path $RepoRoot "PaperPipeline\data\seed.json")
foreach ($s in $SeedCandidates) {
  $sp = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($s)
  if (Test-Path $sp) {
    Write-Host "Uploading seed.json ..."
    scp $sp "${User}@${HostName}:${RemoteDir}/seed.json"
    break
  }
}

$Script = Join-Path $PSScriptRoot "deploy-on-host.sh"
scp $Script "${User}@${HostName}:${RemoteDir}/deploy-on-host.sh"

Write-Host @"

上传完成。请 SSH 登录后执行：
  ssh ${User}@${HostName}
  sed -i 's/\r`$//' ${RemoteDir}/deploy-on-host.sh
  bash ${RemoteDir}/deploy-on-host.sh
  nano /opt/papermate/backend/.env   # 首次：填 LLM Key / AUTH_SECRET
  systemctl restart papermate-backend

详见 docs/服务器运维与更新.md
"@
