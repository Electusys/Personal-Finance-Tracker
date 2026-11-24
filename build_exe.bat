@echo off
setlocal
cd /d "%~dp0"

echo Installing build dependencies...
python -m pip install -r requirements.txt pyinstaller -q
if errorlevel 1 exit /b 1

echo Cleaning previous build...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo Building PersonalFinanceTracker.exe ...
python -m PyInstaller --noconfirm PersonalFinanceTracker.spec
if errorlevel 1 exit /b 1

if exist .env (
  copy /Y .env "dist\PersonalFinanceTracker\.env" >nul
  echo Copied local .env next to the exe.
) else (
  echo No .env found. Copy .env.example to dist\PersonalFinanceTracker\.env and add GEMINI_API_KEY.
)

echo.
echo Done: dist\PersonalFinanceTracker\PersonalFinanceTracker.exe
echo Keep .env next to the exe for Gemini chat.
endlocal
