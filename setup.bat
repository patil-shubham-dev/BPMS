@echo off
rem One time setup for the bus pass project.
rem Installs Git, Python and the GCC compiler with winget, adds Flask,
rem then builds buspass.exe from buspass.c.
rem Run it by double clicking this file.

cd /d "%~dp0"

echo ==========================================
echo  Bus pass project - setup
echo ==========================================
echo.

where winget >nul 2>nul
if errorlevel 1 (
    echo winget was not found.
    echo Open the Microsoft Store, install "App Installer", then run this file again.
    pause
    exit /b 1
)

set WINGET=winget install --exact --source winget --accept-source-agreements --accept-package-agreements --id

rem Git is not needed by the app. It is needed by the code editor's terminal,
rem and it also gives you the git command.
where git >nul 2>nul
if errorlevel 1 %WINGET% Git.Git

rem Python runs server.py
python --version >nul 2>nul
if errorlevel 1 %WINGET% Python.Python.3.13

rem GCC compiles buspass.c into buspass.exe
where gcc >nul 2>nul
if errorlevel 1 %WINGET% BrechtSanders.WinLibs.POSIX.UCRT

rem A program is only on PATH after a new window is opened, so stop here
rem when something was just installed and ask for one more run.
where gcc >nul 2>nul
if errorlevel 1 (
    echo.
    echo GCC was just installed. Close this window, open a new one and run setup.bat again.
    pause
    exit /b 1
)

python --version >nul 2>nul
if errorlevel 1 (
    echo.
    echo Python was just installed. Close this window, open a new one and run setup.bat again.
    pause
    exit /b 1
)

echo Installing Flask...
python -m pip install --upgrade pip
python -m pip install flask
if errorlevel 1 (
    echo.
    echo Flask could not be installed, see the message above.
    pause
    exit /b 1
)

echo Building buspass.exe...
gcc buspass.c -o buspass.exe
if errorlevel 1 (
    echo.
    echo buspass.exe could not be built, see the message above.
    pause
    exit /b 1
)

echo.
echo All ready.
echo   1. Start the app:      python server.py
echo   2. Open in browser:    http://127.0.0.1:5000
echo.
pause
