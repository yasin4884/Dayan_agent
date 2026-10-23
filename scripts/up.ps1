# بالا آوردن کل استک دایان با Docker
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

if (-not (Test-Path .env)) {
  Copy-Item .env.example .env
  Write-Host "ساخته شد: .env از .env.example — JWT_SECRET را عوض کن."
}

# آزاد کردن پورت‌های رایج لوکال قبل از bind داکر
foreach ($port in 3000, 3001, 4000, 8000, 5433, 6379, 6333, 7233, 8080, 27018) {
  Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
    ForEach-Object {
      try { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } catch {}
    }
}

Write-Host "docker compose up -d --build ..."
docker compose up -d --build
docker compose ps
Write-Host ""
Write-Host "دانشجو  http://localhost:3000"
Write-Host "ادمین   http://localhost:3001"
Write-Host "دولوپر  http://localhost:4000"
Write-Host "API     http://localhost:8000/docs"
Write-Host "Temporal UI http://localhost:8080"
