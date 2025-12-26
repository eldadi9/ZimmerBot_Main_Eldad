# PowerShell script להרצת בדיקת שלב 3
# שימוש: .\database\run_check_stage3.ps1

# תיקון encoding ל-UTF-8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Stage 3: Pricing Engine Tests" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# בדוק אם יש venv
$venvPath = "..\venv\Scripts\Activate.ps1"
$venvPath2 = "..\.venv\Scripts\Activate.ps1"

if (Test-Path $venvPath) {
    Write-Host "Activating virtual environment..." -ForegroundColor Yellow
    & $venvPath
} elseif (Test-Path $venvPath2) {
    Write-Host "Activating virtual environment..." -ForegroundColor Yellow
    & $venvPath2
} else {
    Write-Host "Warning: Virtual environment not found" -ForegroundColor Yellow
    Write-Host "Continuing anyway..." -ForegroundColor Yellow
    Write-Host ""
}

# עבור לתיקיית database
Set-Location $PSScriptRoot

# הרץ את הבדיקה
Write-Host "Running tests..." -ForegroundColor Green
Write-Host ""

$env:PYTHONIOENCODING = "utf-8"
python check_stage3.py

$exitCode = $LASTEXITCODE

Write-Host ""
if ($exitCode -eq 0) {
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "SUCCESS: All tests passed!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
} else {
    Write-Host "========================================" -ForegroundColor Red
    Write-Host "FAIL: Some tests failed" -ForegroundColor Red
    Write-Host "========================================" -ForegroundColor Red
}

Write-Host ""
Write-Host "Press Enter to continue..."
Read-Host

exit $exitCode

