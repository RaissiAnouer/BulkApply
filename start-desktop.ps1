Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  Launching AutoApply Desktop Application..." -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
Set-Location -Path $PSScriptRoot
if (Test-Path "$PSScriptRoot\backend\venv\Scripts\python.exe") {
    & "$PSScriptRoot\backend\venv\Scripts\python.exe" "$PSScriptRoot\desktop_app.py"
} else {
    python "$PSScriptRoot\desktop_app.py"
}
