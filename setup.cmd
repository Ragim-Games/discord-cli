@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe python -m venv .venv
if errorlevel 1 exit /b 1
.venv\Scripts\python -m pip install -r requirements.txt
if errorlevel 1 exit /b 1
rem Upstream 0.1.1 requires >=2.2.0 but the current core is 2.2.0a.
.venv\Scripts\python -m pip install --no-deps discord-native-voice==0.1.1
if errorlevel 1 exit /b 1
echo Setup complete. Run start.cmd.
