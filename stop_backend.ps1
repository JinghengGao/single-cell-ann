$ErrorActionPreference = "Stop"

Get-NetTCPConnection -LocalPort 5000 -State Listen -ErrorAction SilentlyContinue |
ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }

Get-CimInstance Win32_Process |
Where-Object { $_.Name -eq "python.exe" -and $_.CommandLine -like "*backend.app*" } |
ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
