@echo off
REM Build the Nazzil portable exe with PyInstaller.
REM Run from this directory:   build.bat

pip install pyinstaller
if errorlevel 1 (
    echo Failed to install pyinstaller.
    exit /b 1
)

if not exist assets\icon.png (
    echo Generating icon...
    python generate_icon.py
)

echo Fetching bundled tools (ffmpeg / aria2c)...
python fetch_binaries.py

pyinstaller nazzil.spec
if errorlevel 1 (
    echo Build failed.
    exit /b 1
)

echo.
echo Build complete: dist\Nazzil.exe
pause
