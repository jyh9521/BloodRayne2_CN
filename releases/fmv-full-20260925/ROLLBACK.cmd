@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0rollback.ps1"
set "result=%errorlevel%"
pause
exit /b %result%
