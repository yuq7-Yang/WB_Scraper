@echo off
setlocal

pushd "%~dp0" || (
    echo Failed to enter the project directory.
    echo.
    pause
    exit /b 1
)

where python >nul 2>nul
if errorlevel 1 (
    echo Python was not found. Please install Python or make sure the python command is available.
    echo.
    pause
    exit /b 1
)

echo Starting Weibo dashboard...
echo Project directory: %CD%
echo.

python -m weibo_bot.dashboard
set "EXIT_CODE=%ERRORLEVEL%"

popd

if not "%EXIT_CODE%"=="0" (
    echo.
    echo Dashboard startup failed. Exit code: %EXIT_CODE%
    pause
)

exit /b %EXIT_CODE%
