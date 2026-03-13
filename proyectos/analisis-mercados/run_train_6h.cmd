@echo off
setlocal

cd /d "C:\Users\Fernando\.openclaw\workspace\proyectos\analisis-mercados"

if not exist "logs" mkdir "logs"

set "LOCK=logs\history_train.lock"
set "LOG=logs\history_update_and_train_schtasks.log"
set "JOB=scripts\run_history_update_and_train_hidden.ps1"

if exist "%LOCK%" (
  echo [%date% %time%] LOCK existe. No lanzo job.>> "%LOG%"
  exit /b 0
)

echo [%date% %time%] START scheduler job=%JOB%>> "%LOG%"
echo running > "%LOCK%"

powershell -NoProfile -ExecutionPolicy Bypass -File "%CD%\%JOB%" >> "%LOG%" 2>&1
set "EC=%errorlevel%"

del "%LOCK%" >nul 2>&1
echo [%date% %time%] END exit=%EC%>> "%LOG%"
exit /b %EC%

endlocal
