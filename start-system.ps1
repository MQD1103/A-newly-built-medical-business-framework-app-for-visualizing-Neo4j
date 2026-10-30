$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Backend = Join-Path $Root 'backend'
$Frontend = Join-Path $Root 'frontend'
$VenvPython = Join-Path $Backend '.venv\Scripts\python.exe'
$VenvDir = Join-Path $Backend '.venv'
$NodeModules = Join-Path $Frontend 'node_modules'
$PipMirror = 'https://pypi.tuna.tsinghua.edu.cn/simple'
$BackendHost = '127.0.0.1'
$BackendPort = 8001
$FrontendHost = '127.0.0.1'
$FrontendPort = 5174

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

function Open-Frontend([string]$Url) {
  # 优先系统默认浏览器；失败时退回 Edge / 资源管理器
  try {
    Start-Process $Url
    return $true
  } catch {}
  $edge = Join-Path ${env:ProgramFiles(x86)} 'Microsoft\Edge\Application\msedge.exe'
  if (Test-Path -LiteralPath $edge) {
    try {
      Start-Process -FilePath $edge -ArgumentList $Url
      return $true
    } catch {}
  }
  try {
    Start-Process 'explorer.exe' -ArgumentList $Url
    return $true
  } catch {}
  return $false
}

function Get-SystemPython {
  foreach ($name in @('py', 'python')) {
    $cmd = Get-Command $name -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd }
  }
  return $null
}

Write-Step '正在检查运行环境...'

if (-not (Test-Path -LiteralPath (Join-Path $Frontend 'package.json'))) {
  Write-Host "[错误] 找不到前端项目: $Frontend" -ForegroundColor Red
  exit 1
}
if (-not (Test-Path -LiteralPath (Join-Path $Backend 'requirements.txt'))) {
  Write-Host "[错误] 找不到后端项目: $Backend" -ForegroundColor Red
  exit 1
}

$npm = Get-Command npm -ErrorAction SilentlyContinue
if (-not $npm) {
  # 本机便携版 Node.js 兜底（未加入系统 PATH 时也能启动）
  $NodeFallback = 'C:\Users\32464\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\work-mode-projects\6ad4abbe301fd88a4999ab4e\nodejs'
  if (Test-Path -LiteralPath (Join-Path $NodeFallback 'npm.cmd')) {
    $env:Path = "$NodeFallback;$env:Path"
    $npm = Get-Command npm -ErrorAction SilentlyContinue
  }
}
if (-not $npm) {
  Write-Host '[错误] 未找到 npm。请先安装 Node.js（勾选加入 PATH）后重试。' -ForegroundColor Red
  exit 1
}

# 首次：自动创建后端虚拟环境并安装依赖
if (-not (Test-Path -LiteralPath $VenvPython)) {
  Write-Step '首次运行：正在创建后端虚拟环境并安装依赖（可能需要几分钟）...'
  $py = Get-SystemPython
  if (-not $py) {
    Write-Host '[错误] 未找到 Python。请安装 Python 3.10+ 并勾选「Add to PATH」。' -ForegroundColor Red
    exit 1
  }
  if ($py.Name -eq 'py.exe') {
    & $py.Source -3 -m venv $VenvDir
  } else {
    & $py.Source -m venv $VenvDir
  }
  if (-not (Test-Path -LiteralPath $VenvPython)) {
    Write-Host '[错误] 虚拟环境创建失败。' -ForegroundColor Red
    exit 1
  }
  & $VenvPython -m pip install --upgrade pip -i $PipMirror
  & $VenvPython -m pip install -r (Join-Path $Backend 'requirements.txt') -i $PipMirror --timeout 60 --retries 5
  Write-Host '[成功] 后端依赖已安装。' -ForegroundColor Green
}

# 首次：自动安装前端依赖
if (-not (Test-Path -LiteralPath $NodeModules)) {
  Write-Step '首次运行：正在安装前端依赖 npm install（可能需要几分钟）...'
  Push-Location $Frontend
  try {
    & npm.cmd install
    if ($LASTEXITCODE -ne 0) { throw "npm install 失败，退出码 $LASTEXITCODE" }
  } finally {
    Pop-Location
  }
  Write-Host '[成功] 前端依赖已安装。' -ForegroundColor Green
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
# 首次装依赖后首次编译可能较慢，多等一会
for ($i = 0; $i -lt 120; $i++) {
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
  Write-Host "[成功] 正在打开前端: $readyUrl" -ForegroundColor Green
  if (-not (Open-Frontend $readyUrl)) {
    Write-Host "[提示] 无法自动打开浏览器，请手动访问: $readyUrl" -ForegroundColor Yellow
  }
  Write-Host ''
  Write-Host "前端: $readyUrl" -ForegroundColor Green
  Write-Host "后端: http://${BackendHost}:${BackendPort}  (接口文档 /docs)" -ForegroundColor Green
  Write-Host '首次打开应看到：节点首页 + COPD 系列课程（售价见详情）。' -ForegroundColor DarkGray
  Write-Host '本机独立运行，关闭本机不影响同事。' -ForegroundColor DarkGray
  Write-Host '停止服务请双击「关闭系统.bat」。' -ForegroundColor DarkGray
  exit 0
}

Write-Host '[错误] 前端未能在约 60 秒内就绪。请查看弹出的黑色 CMD 窗口报错。' -ForegroundColor Red
exit 1
