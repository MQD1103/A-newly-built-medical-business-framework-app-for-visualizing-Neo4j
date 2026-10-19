$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$FrontendHost = '127.0.0.1'
$FrontendPort = 5173
$FrontendUrl = "http://${FrontendHost}:${FrontendPort}/"

function Test-PortListen([int]$Port) {
  try {
    return [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
  } catch {
    return $false
  }
}

if (Test-PortListen $FrontendPort) {
  Write-Host "[打开] 前端已在运行：$FrontendUrl" -ForegroundColor Green
  Start-Process $FrontendUrl
  exit 0
}

Write-Host '[启动] 前端尚未运行，正在启动前后端...' -ForegroundColor Yellow
& (Join-Path $Root 'start-system.ps1')
exit $LASTEXITCODE
