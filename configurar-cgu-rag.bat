@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0configurar-cgu-rag.ps1"
if errorlevel 1 (
  echo.
  echo A configuracao terminou com erro. Leia a mensagem acima.
  pause
)
