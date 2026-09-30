@echo off
rem Double-click to start Vikas Vaani (citizen portal at http://127.0.0.1:8000/, dashboard at /admin).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1" %*
pause
