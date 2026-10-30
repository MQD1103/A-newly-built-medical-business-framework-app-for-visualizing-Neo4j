$ErrorActionPreference = 'SilentlyContinue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$Ports = @(8001, 5174)

function Write-Step([string]$Message, [string]$Color = 'Cyan') {
  Write-Host "[关闭] $Message" -ForegroundColor $Color
}

function Get-ListenPids([int]$Port) {
  $pids = @()
  try {
    $pids += @(
      Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique
    )
  } catch {}
  # fallback: netstat
  $lines = netstat -ano 2>$null | Select-String -Pattern ":$Port\s+.*LISTENING\s+(\d+)$"
  foreach ($m in $lines) {
    if ($m.Matches.Count -gt 0) {
      $pids += [int]$m.Matches[0].Groups[1].Value
    }
  }
  return @($pids | Where-Object { $_ -gt 0 } | Select-Object -Unique)
}

function Stop-Tree([int]$ProcessId) {
  if ($ProcessId -le 0) { return }
  # Kill children first (uvicorn reload workers, npm -> node, etc.)
  Get-CimInstance Win32_Process -Filter "ParentProcessId=$ProcessId" -ErrorAction SilentlyContinue |
    ForEach-Object { Stop-Tree -ProcessId $_.ProcessId }
  Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
}

Write-Step '正在关闭前后端相关进程...'

$killed = @{}
foreach ($port in $Ports) {
  foreach ($pid in (Get-ListenPids $port)) {
    if (-not $killed.ContainsKey($pid)) {
      Write-Host "  - 结束占用端口 $port 的进程 PID=$pid"
      Stop-Tree -ProcessId $pid
      $killed[$pid] = $true
    }
  }
}

# Sweep leftover uvicorn / vite / npm run dev
Get-CimInstance Win32_Process |
  Where-Object {
    $_.CommandLine -and (
      ($_.CommandLine -like '*uvicorn*app.main:app*') -or
      ($_.CommandLine -like '*vite\bin\vite.js*') -or
      (($_.CommandLine -like '*vite.js*') -and ($_.CommandLine -like '*--host*')) -or
      ($_.CommandLine -like '*npm-cli.js*run*dev*') -or
      (($_.CommandLine -like '*npm*run*dev*') -and ($_.CommandLine -like '*frontend*'))
    )
  } |
  ForEach-Object {
    if (-not $killed.ContainsKey($_.ProcessId)) {
      Write-Host "  - 清理残留进程 PID=$($_.ProcessId) ($($_.Name))"
      Stop-Tree -ProcessId $_.ProcessId
      $killed[$_.ProcessId] = $true
    }
  }

Start-Sleep -Seconds 1

$stillBusy = @()
foreach ($port in $Ports) {
  if ((Get-ListenPids $port).Count -gt 0) {
    $stillBusy += $port
  }
}

if ($stillBusy.Count -eq 0) {
  Write-Host '[成功] 端口 8001 / 5174 已释放。' -ForegroundColor Green
  exit 0
}

Write-Host ("[警告] 仍有端口被占用: " + ($stillBusy -join ', ')) -ForegroundColor Yellow
Write-Host '可再运行一次「关闭系统.bat」，或以管理员身份运行。' -ForegroundColor Yellow
exit 1
