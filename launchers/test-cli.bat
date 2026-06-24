@echo off
setlocal

cd /d "%~dp0.."

where uv >nul 2>nul
if errorlevel 1 (
    echo uv is not installed or not available on PATH.
    echo Install uv first, then run this launcher again.
    pause
    exit /b 1
)

uv run test-cli
set EXIT_CODE=%ERRORLEVEL%

echo.
if not "%EXIT_CODE%"=="0" echo test-cli exited with code %EXIT_CODE%
pause
exit /b %EXIT_CODE%
