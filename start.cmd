@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Run setup.cmd first.
  pause
  exit /b 1
)
.venv\Scripts\python -X faulthandler -m discord_cli %*
set "cli_exit=%errorlevel%"
if not "%cli_exit%"=="0" (
  echo.
  echo Discord CLI stopped with error code %cli_exit%. See the error above.
  pause
)
exit /b %cli_exit%
