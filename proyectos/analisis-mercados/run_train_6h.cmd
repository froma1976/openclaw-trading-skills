@echo off
setlocal

cd /d "C:\Users\Fernando\.openclaw\workspace\proyectos\analisis-mercados"

if not exist "logs" mkdir "logs"

set "LOCK=logs\history_train.lock"
set "LOG=logs\history_update_and_train_schtasks.log"
set "JOB=scripts\run_history_update_and_train_hidden.ps1"
set "LOCK_MAX_MINUTES=240"

if exist "%LOCK%" (
  powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$lock = Join-Path (Get-Location) '%LOCK%'; $jobPath = Join-Path (Get-Location) '%JOB%'; $active = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue ^| Where-Object { $_.CommandLine -like ('*' + $jobPath + '*-HiddenChild*') }); if ($active.Count -gt 0) { exit 10 }; if (-not (Test-Path $lock)) { exit 11 }; $ageMin = ((Get-Date) - (Get-Item $lock).LastWriteTime).TotalMinutes; if ($ageMin -ge %LOCK_MAX_MINUTES%) { Remove-Item $lock -Force -ErrorAction SilentlyContinue; exit 12 }; exit 13"
  set "LOCK_STATE=%errorlevel%"
  if "%LOCK_STATE%"=="10" (
    echo [%date% %time%] LOCK activo con proceso en ejecucion. No lanzo job.>> "%LOG%"
    exit /b 0
  )
  if "%LOCK_STATE%"=="12" (
    echo [%date% %time%] LOCK stale detectado. Se elimina y se reintenta.>> "%LOG%"
  ) else if exist "%LOCK%" (
    echo [%date% %time%] LOCK reciente detectado. No lanzo job.>> "%LOG%"
    exit /b 0
  )
)

echo [%date% %time%] START scheduler job=%JOB%>> "%LOG%"
> "%LOCK%" (
  echo started_at=%date% %time%
  echo host=%COMPUTERNAME%
  echo job=%JOB%
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%CD%\%JOB%" -HiddenChild >> "%LOG%" 2>&1
set "EC=%errorlevel%"

del "%LOCK%" >nul 2>&1
echo [%date% %time%] END exit=%EC%>> "%LOG%"
exit /b %EC%

endlocal
