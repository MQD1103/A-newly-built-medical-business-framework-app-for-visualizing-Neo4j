$ErrorActionPreference = 'SilentlyContinue'
Write-Host '[Campus] stopping related processes...' -ForegroundColor Cyan

foreach ($port in 8000, 5173) {
  Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
    ForEach-Object {
      Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
    }
}

Get-CimInstance Win32_Process |
  Where-Object {
    $_.CommandLine -and (
      $_.CommandLine -like '*uvicorn*app.main:app*' -or
      $_.CommandLine -like '*vite\bin\vite.js*' -or
      $_.CommandLine -like '*npm-cli.js*run*dev*'
    )
  } |
  ForEach-Object {
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
  }

Write-Host 'Tried to free ports 8000 / 5173.' -ForegroundColor Green
