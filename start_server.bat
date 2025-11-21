@echo off

REM ========================================
REM 빠른 편집 모드(QuickEdit) 강제 비활성화
REM ========================================
REG ADD "HKCU\Console" /v QuickEdit /t REG_DWORD /d 0 /f > nul

REM ========================================
REM 중복 실행 체크
REM ========================================
netstat -aon | findstr :23100 | findstr LISTENING >nul
if %errorlevel%==0 (
    echo.
    echo [ERROR] Flask server is already running on port 23100!
    echo Please run stop_server.bat first.
    echo.
    pause
    exit /b 1
)

netstat -aon | findstr :23101 | findstr LISTENING >nul
if %errorlevel%==0 (
    echo.
    echo [ERROR] ComfyUI server is already running on port 23101!
    echo Please run stop_server.bat first.
    echo.
    pause
    exit /b 1
)

REM ========================================
REM 경로 설정 (여기만 수정하세요)
REM ========================================
set FLASK_VENV=.venv\Scripts\activate
set FLASK_APP=server.py

set COMFYUI_VENV=ComfyUI\.venv\Scripts\activate
set COMFYUI_MAIN=ComfyUI\main.py

REM ========================================
REM 서버 시작
REM ========================================
REM ComfyUI 서버 시작
start "ComfyUI Server" cmd /c "call %COMFYUI_VENV% && python %COMFYUI_MAIN% --port 23101 --cuda-device 1"

REM Flask 서버 시작 (현재 콘솔에서 실행)
call %FLASK_VENV%
python %FLASK_APP%