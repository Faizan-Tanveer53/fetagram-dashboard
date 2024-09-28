Write-Host "Starting Fetagram Enterprise Multi-Service Platform..." -ForegroundColor Cyan

$root = Split-Path -Parent $MyInvocation.MyCommand.Path

Start-Process python -ArgumentList "main.py" -WorkingDirectory "$root\backend" -WindowStyle Hidden
Start-Process python -ArgumentList "-m http.server 3000" -WorkingDirectory "$root\client-web" -WindowStyle Hidden
Start-Process python -ArgumentList "-m http.server 3001" -WorkingDirectory "$root\admin-dashboard" -WindowStyle Hidden

Write-Host "✅ Backend REST & WebSocket API : http://localhost:8000" -ForegroundColor Green
Write-Host "✅ Fetagram Client Web App     : http://localhost:3000" -ForegroundColor Green
Write-Host "✅ Isolated Admin Dashboard    : http://localhost:3001" -ForegroundColor Green
