$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Backend = Join-Path $Root 'backend'
$Frontend = Join-Path $Root 'frontend'
$VenvPython = Join-Path $Backend '.venv\Scripts\python.exe'
$BackendHost = '127.0.0.1'
$BackendPort = 8000
$FrontendHost = '127.0.0.1'
$FrontendPort = 5173

function Test-PortListen([int]$Port) {
  try {
    return [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
  } catch {
    return $false
  }
}

function Write-Step([string]$Message, [string]$Color = 'Cyan') {
  Write-Host "[启动] $Message" -ForegroundColor $Color
}

Write-Step '正在检查运行环境...'

if (-not (Test-Path -LiteralPath $VenvPython)) {
  Write-Host "[错误] 找不到后端虚拟环境: $VenvPython" -ForegroundColor Red
  Write-Host '请先在 backend 目录创建 .venv 并安装依赖。' -ForegroundColor Yellow
  exit 1
}
if (-not (Test-Path -LiteralPath (Join-Path $Frontend 'package.json'))) {
  Write-Host "[错误] 找不到前端项目: $Frontend" -ForegroundColor Red
  exit 1
}
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
  Write-Host '[错误] 未找到 npm。请安装 Node.js 并加入 PATH。' -ForegroundColor Red
  exit 1
}

# 每人本机独立运行，默认只监听 127.0.0.1
if (-not (Test-PortListen $BackendPort)) {
  Write-Step "启动后端 http://${BackendHost}:${BackendPort} ..."
  $backendCmd = ".venv\Scripts\python.exe -m uvicorn app.main:app --reload --host $BackendHost --port $BackendPort"
  Start-Process -FilePath 'cmd.exe' `
    -ArgumentList '/k', "title 小医-后端:$BackendPort && $backendCmd" `
    -WorkingDirectory $Backend
} else {
  Write-Host "[提示] 后端已在端口 $BackendPort 运行，跳过启动。" -ForegroundColor Yellow
}

if (-not (Test-PortListen $FrontendPort)) {
  Write-Step "启动前端 http://${FrontendHost}:${FrontendPort} ..."
  $frontendCmd = "npm run dev -- --host $FrontendHost --port $FrontendPort"
  Start-Process -FilePath 'cmd.exe' `
    -ArgumentList '/k', "title 小医-前端:$FrontendPort && $frontendCmd" `
    -WorkingDirectory $Frontend
} else {
  Write-Host "[提示] 前端已在端口 $FrontendPort 运行，跳过启动。" -ForegroundColor Yellow
}

Write-Step '等待前端就绪...'
$urls = @(
  "http://${FrontendHost}:${FrontendPort}/",
  "http://localhost:${FrontendPort}/"
)
$readyUrl = $null
for ($i = 0; $i -lt 60; $i++) {
  foreach ($url in $urls) {
    try {
      $resp = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 2
      if ($resp.StatusCode -ge 200) {
        $readyUrl = $url
        break
      }
    } catch {
      # not ready yet
    }
  }
  if ($readyUrl) { break }
  Start-Sleep -Milliseconds 500
}

if ($readyUrl) {
  Write-Host "[成功] 正在打开浏览器: $readyUrl" -ForegroundColor Green
  Start-Process $readyUrl
  Write-Host ''
  Write-Host "前端: $readyUrl" -ForegroundColor Green
  Write-Host "后端: http://${BackendHost}:${BackendPort}  (接口文档 /docs)" -ForegroundColor Green
  Write-Host '本机独立运行，关闭本机不影响同事。' -ForegroundColor DarkGray
  Write-Host '停止服务请双击「关闭系统.bat」。' -ForegroundColor DarkGray
  exit 0
}

Write-Host '[错误] 前端 30 秒内未就绪。请查看弹出的黑色 CMD 窗口报错。' -ForegroundColor Red
exit 1
