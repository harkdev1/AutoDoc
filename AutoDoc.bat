@echo off
cd /d "%~dp0"
powershell.exe -NoExit -ExecutionPolicy Bypass -Command "& '%~dp0.venv\Scripts\Activate.ps1'"