@echo off
echo Stopping Flask and ComfyUI servers...

REM Flask 서버 종료 (포트 23100)
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :23100 ^| findstr LISTENING') do (
    set PID=%%a
    setlocal enabledelayedexpansion
    echo Killing Flask server (PID: !PID!)

    REM 부모 프로세스(cmd.exe) PID 찾기
    for /f "tokens=2" %%p in ('wmic process where "ProcessId=!PID!" get ParentProcessId /format:list ^| findstr "="') do (
        set PARENT=%%p
        echo Killing parent process (PID: !PARENT!)
        taskkill /F /T /PID !PARENT! 2>nul
    )

    taskkill /F /T /PID !PID! 2>nul
    endlocal
)

REM ComfyUI 서버 종료 (포트 23101)
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :23101 ^| findstr LISTENING') do (
    set PID=%%a
    setlocal enabledelayedexpansion
    echo Killing ComfyUI server (PID: !PID!)

    REM 부모 프로세스(cmd.exe) PID 찾기
    for /f "tokens=2" %%p in ('wmic process where "ProcessId=!PID!" get ParentProcessId /format:list ^| findstr "="') do (
        set PARENT=%%p
        echo Killing parent process (PID: !PARENT!)
        taskkill /F /T /PID !PARENT! 2>nul
    )

    taskkill /F /T /PID !PID! 2>nul
    endlocal
)

echo ========================================
echo Both servers and terminals stopped!
echo ========================================