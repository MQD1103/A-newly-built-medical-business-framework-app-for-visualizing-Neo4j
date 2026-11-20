$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Backend = Join-Path $Root 'backend'
$FrontendHost = '127.0.0.1'
$BackendHost = '127.0.0.1'
$FrontendPort = 5173
$BackendPort = 8000
$FrontendUrl = "http://${FrontendHost}:${FrontendPort}/"

function Test-PortListen([int]$Port) {
  try {
    return [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
  } catch {
    return $false
  }
}

function Test-BackendReady([int]$Port) {
  try {
    $resp = Invoke-WebRequest -Uri "http://${BackendHost}:${Port}/api/health" -UseBasicParsing -TimeoutSec 2
    return ($resp.StatusCode -ge 200)
  } catch {
    return $false
  }
}

# 前端在跑但后端没跑时，登录一定会失败，所以这里必须两个都检查
if (-not (Test-PortListen $BackendPort)) {
  Write-Host "[启动] 后端未运行，正在启动 http://${BackendHost}:${BackendPort} ..." -ForegroundColor Yellow
  $venvPython = Join-Path $Backend '.venv\Scripts\python.exe'
  if (-not (Test-Path -LiteralPath $venvPython)) {
    Write-Host '[错误] 找不到后端虚拟环境，请先运行 start-system.ps1 初始化。' -ForegroundColor Red
    exit 1
  }
  $backendCmd = ".venv\Scripts\python.exe -m uvicorn app.main:app --reload --host $BackendHost --port $BackendPort"
  Start-Process -FilePath 'cmd.exe' `
    -ArgumentList '/k', "title 小医-后端:$BackendPort && $backendCmd" `
    -WorkingDirectory $Backend

  Write-Host '[等待] 后端启动中...' -ForegroundColor Yellow
  $ready = $false
  for ($i = 0; $i -lt 60; $i++) {
    if (Test-BackendReady $BackendPort) { $ready = $true; break }
    Start-Sleep -Milliseconds 500
  }
  if (-not $ready) {
    Write-Host '[警告] 后端 30 秒内未就绪，请查看弹出的黑色窗口报错（常见原因：依赖缺失）。' -ForegroundColor Red
  } else {
    Write-Host '[成功] 后端已就绪。' -ForegroundColor Green
  }
} else {
  Write-Host "[提示] 后端已在 $BackendPort 端口运行。" -ForegroundColor DarkGray
}

if (Test-PortListen $FrontendPort) {
  Write-Host "[打开] 前端已在运行：$FrontendUrl" -ForegroundColor Green
  Start-Process $FrontendUrl
  exit 0
}

Write-Host '[启动] 前端尚未运行，正在启动前后端...' -ForegroundColor Yellow
& (Join-Path $Root 'start-system.ps1')
exit $LASTEXITCODE
