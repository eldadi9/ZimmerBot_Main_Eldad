@echo off
setlocal

set "P=C:\Users\Master_PC\Desktop\IPtv_projects\Projects Eldad\ZimmerBot_Workspace\ZimmerBot_Main_Eldad"

echo ==============================
echo Project: %P%
echo ZIP will be: zimmerbot_upload.zip
echo ==============================

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$P='%P%';" ^
  "Set-Location -Path $P;" ^
  "$secrets = @('.\data\token.json','.\data\token_api.json','.\data\credentials.json','.\.env');" ^
  "$found = @();" ^
  "foreach($f in $secrets){ if(Test-Path $f){ $found += $f } }" ^
  "if($found.Count -gt 0){" ^
  "  Write-Host 'WARNING: Secret files exist (will NOT be zipped by this script):' -ForegroundColor Yellow;" ^
  "  $found | ForEach-Object { Write-Host (' - ' + $_) -ForegroundColor Yellow }" ^
  "  Write-Host 'Make sure you do NOT upload these files.' -ForegroundColor Yellow;" ^
  "}" ^
  "Compress-Archive -Path .\src,.\database,.\docs,.\tools,.\data\features_catalog.json,.\README.md,.\requirements.txt,.\.gitignore -DestinationPath .\zimmerbot_upload.zip -Force;" ^
  "Write-Host 'Done. Created:' (Join-Path $P 'zimmerbot_upload.zip');"

echo ==============================
echo Press Enter to close...
pause >nul
endlocal
