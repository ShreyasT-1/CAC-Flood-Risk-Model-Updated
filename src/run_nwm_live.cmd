@echo off
rem Hourly NWM archiver wrapper (Task Scheduler). Catches up the last 72 h; idempotent (existing cycles skipped).
set LOGD=%~dp0..\data\forecasts\logs
if not exist "%LOGD%" mkdir "%LOGD%"
cd /d %~dp0
echo [%date% %time%] start >> "%LOGD%\live_task.log"
"C:\Users\nisha\AppData\Local\Python\pythoncore-3.14-64\python.exe" nwm_backfill.py 72 >> "%LOGD%\live_task.log" 2>&1
echo [%date% %time%] exit %errorlevel% >> "%LOGD%\live_task.log"
