$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Backend = Join-Path $Root 'backend'
$Frontend = Join-Path $Root 'frontend'
$VenvPython = Join-Path $Backend '.venv\Scripts\python.exe'

function Test-PortListen([int]$Port) {
  try {
    return [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
  } catch {
    return $false
  }
}

Write-Host '[Campus] checking environment...' -ForegroundColor Cyan

if (-not (Test-Path -LiteralPath $VenvPython)) {
  Write-Host "Missing backend venv: $VenvPython" -ForegroundColor Red
  Write-Host 'Create venv and install deps in backend first.'
  exit 1
}
if (-not (Test-Path -LiteralPath (Join-Path $Frontend 'package.json'))) {
  Write-Host "Missing frontend: $Frontend" -ForegroundColor Red
  exit 1
}
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
  Write-Host 'npm not found. Install Node.js and add it to PATH.' -ForegroundColor Red
  exit 1
}

# 默认只监听本机：每人各自跑自己的后端，不占用同事电脑
if (-not (Test-PortListen 8000)) {
  Write-Host '[Campus] starting backend http://127.0.0.1:8000 ...' -ForegroundColor Cyan
  # Use python -m uvicorn: uvicorn.exe launcher can fail silently on some Windows setups
  Start-Process -FilePath 'cmd.exe' `
    -ArgumentList '/k', '.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000' `
    -WorkingDirectory $Backend
} else {
  Write-Host '[Campus] backend already listening on 8000' -ForegroundColor Yellow
}

if (-not (Test-PortListen 5173)) {
  Write-Host '[Campus] starting frontend http://127.0.0.1:5173 ...' -ForegroundColor Cyan
  Start-Process -FilePath 'cmd.exe' `
    -ArgumentList '/k', 'npm run dev -- --host 127.0.0.1' `
    -WorkingDirectory $Frontend
} else {
  Write-Host '[Campus] frontend already listening on 5173' -ForegroundColor Yellow
}

Write-Host '[Campus] waiting for frontend...' -ForegroundColor Cyan
$urls = @('http://127.0.0.1:5173/', 'http://localhost:5173/')
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
  Write-Host '[Campus] opening browser...' -ForegroundColor Green
  Start-Process $readyUrl
  Write-Host "Started: $readyUrl"
  Write-Host 'Backend API: http://127.0.0.1:8000  (docs: /docs)' -ForegroundColor Cyan
  Write-Host '本机独立运行：关电脑也不影响同事（他们用自己的本机服务）。' -ForegroundColor DarkGray
  Write-Host 'Stop with 关闭系统.bat'
  exit 0
}

Write-Host 'Frontend not ready in 30s. Check the black cmd windows for errors.' -ForegroundColor Red
exit 1
