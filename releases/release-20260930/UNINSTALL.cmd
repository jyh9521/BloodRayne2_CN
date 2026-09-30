@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0manage.ps1" -Mode Rollback %*
if errorlevel 1 (echo ROLLBACK FAILED & pause & exit /b 1)
pause
