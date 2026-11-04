@echo off
cd /d "%~dp0"
start "" http://localhost:8095
.venv\Scripts\python.exe -m app
