@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0manage.ps1" -Mode Install %*
if errorlevel 1 (echo INSTALL FAILED & pause & exit /b 1)
echo Installation complete. Select Russian text in game.
pause
