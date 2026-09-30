@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Program henuz kurulmamis. KUR.bat dosyasina cift tiklayin.
  pause
  exit /b
)
rem Zaten calisiyorsa sadece tarayiciyi ac
netstat -ano | findstr ":8000" | findstr "LISTENING" >nul && (
  if /i not "%1"=="/arka" start "" http://localhost:8000
  exit /b
)
if /i not "%1"=="/arka" (
  echo Program calisiyor: http://localhost:8000
  echo Bu pencereyi kapatirsaniz program ve gunluk tarama durur.
  start "" http://localhost:8000
)
if not exist veri mkdir veri
.venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 >> veri\sunucu.log 2>&1
