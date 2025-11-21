@echo off
setlocal

REM 현재 폴더에서 uv venv 생성 및 의존성 설치
echo =================================================
echo Step 1: Setting up virtual environment and installing dependencies
echo =================================================
pip install uv
uv venv --python 3.10
if errorlevel 1 (
    echo ❌ Failed to create virtual environment. Exiting.
    pause
    exit /b 1
)

uv pip install -r requirements.txt
if errorlevel 1 (
    echo ❌ Failed to install requirements.txt. Exiting.
    pause
    exit /b 1
)

uv pip install git+https://github.com/openai/CLIP.git
if errorlevel 1 (
    echo ❌ Failed to install CLIP. Exiting.
    pause
    exit /b 1
)

uv pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
if errorlevel 1 (
    echo ❌ Failed to install PyTorch. Exiting.
    pause
    exit /b 1
)

REM ComfyUI 폴더로 이동하여 새로운 venv 생성 및 의존성 설치
echo =================================================
echo Step 2: Setting up a new virtual environment in ComfyUI folder
echo =================================================
cd ComfyUI

REM 새로운 가상 환경 생성
uv venv .venv
if errorlevel 1 (
    echo ❌ Failed to create a new virtual environment in ComfyUI folder. Exiting.
    pause
    exit /b 1
)

REM ComfyUI 의존성 설치
if not exist requirements.txt (
    echo ❌ requirements.txt not found in ComfyUI folder. Exiting.
    pause
    exit /b 1
)

uv pip install -r requirements.txt
if errorlevel 1 (
    echo ❌ Failed to install requirements.txt in ComfyUI folder. Exiting.
    pause
    exit /b 1
)

uv pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
if errorlevel 1 (
    echo ❌ Failed to install PyTorch in ComfyUI folder. Exiting.
    pause
    exit /b 1
)

REM ComfyUI-Manager 폴더로 이동하여 install all 실행
echo =================================================
echo Step 3: Installing all custom nodes using ComfyUI-Manager
echo =================================================

uv run python custom_node_install.py
if errorlevel 1 (
    echo ❌ Failed to install all custom nodes. Exiting.
    pause
    exit /b 1
)

echo =================================================
echo All steps completed successfully!
echo =================================================
pause
endlocal