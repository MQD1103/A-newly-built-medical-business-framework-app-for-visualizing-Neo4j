$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Backend = Join-Path $Root "backend"
Set-Location $Backend
& (Join-Path $Backend ".venv\Scripts\python.exe") -m uvicorn app.main:app --host 127.0.0.1 --port 8001 *>> (Join-Path $Backend "uvicorn.log")