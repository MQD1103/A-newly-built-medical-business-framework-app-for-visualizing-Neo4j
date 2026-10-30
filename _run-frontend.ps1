$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Frontend = Join-Path $Root "frontend"
$NodeDir = "C:\Users\32464\AppData\Roaming\TRAE SOLO CN\ModularData\ai-agent\work-mode-projects\6ad4abbe301fd88a4999ab4e\nodejs"
$env:Path = "$NodeDir;$env:Path"
Set-Location $Frontend
& (Join-Path $NodeDir "npm.cmd") run dev -- --host 127.0.0.1 --port 5174 *>> (Join-Path $Frontend "vite.log")