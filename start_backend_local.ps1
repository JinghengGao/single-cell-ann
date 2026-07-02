$ErrorActionPreference = "Stop"

$workspace = "D:\nankai\software\final"
$python = "D:\developtools\anaconda\envs\single-cell-ann\python.exe"

Get-NetTCPConnection -LocalPort 5000 -State Listen -ErrorAction SilentlyContinue |
ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }

Get-CimInstance Win32_Process |
Where-Object { $_.Name -eq "python.exe" -and $_.CommandLine -like "*backend.app*" } |
ForEach-Object { Stop-Process -Id $_.ProcessId -Force }

Start-Sleep -Seconds 1

$env:SCANN_DEBUG = "false"
$env:SCANN_LLM_PROVIDER = "local"
$env:SCANN_LLM_API_URL = "http://127.0.0.1:11434/v1/chat/completions"
$env:SCANN_LLM_MODEL = "qwen3:8b"
$env:SCANN_LLM_API_KEY = ""

Set-Location $workspace
& $python backend_run_local.py
