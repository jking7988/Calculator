@echo on
setlocal ENABLEDELAYEDEXPANSION

REM =========================================
REM Double Oak: Update & Launch (Debug Mode)
REM - Keeps window open on errors
REM - Echoes each step
REM - Logs to .\run.log for review
REM =========================================

REM Go to this script's folder (project root)
cd /d "%~dp0"

set LOG=run.log
echo === %DATE% %TIME% Starting update_and_launch_debug.bat === > "%LOG%"

REM --- Prefer venv Python if available ---
set PYEXE=python
if exist ".venv\Scripts\python.exe" (
  set "PYEXE=.venv\Scripts\python.exe"
  echo Using venv Python: %CD%\.venv\Scripts\python.exe >> "%LOG%"
) else (
  echo Using system Python on PATH >> "%LOG%"
)

REM --- Verify Python works ---
"%PYEXE%" --version 1>>"%LOG%" 2>&1
if errorlevel 1 (
  echo [ERROR] Python not found or not runnable. >> "%LOG%"
  echo.
  echo Python not found. Make sure Python is installed or that .venv exists.
  echo Press any key to exit...
  pause >nul
  exit /b 1
)

REM --- Activate venv if present (for PATH/Streamlit convenience) ---
if exist ".venv\Scripts\activate.bat" (
  call ".venv\Scripts\activate.bat"
)

REM --- Check Streamlit is installed ---
"%PYEXE%" -c "import streamlit,sys; print(streamlit.__version__)" 1>>"%LOG%" 2>&1
if errorlevel 1 (
  echo [INFO] Installing Streamlit into the active Python... >> "%LOG%"
  "%PYEXE%" -m pip install --upgrade pip 1>>"%LOG%" 2>&1
  "%PYEXE%" -m pip install streamlit 1>>"%LOG%" 2>&1
  if errorlevel 1 (
    echo [ERROR] Failed to install Streamlit. See run.log. >> "%LOG%"
    echo.
    echo Failed to install Streamlit. See run.log for details.
    echo Press any key to exit...
    pause >nul
    exit /b 1
  )
)

REM --- Pick codemod script (prefer full UI updater) ---
set "SCRIPT=apply_full_ui_updates.py"
if not exist "%SCRIPT%" (
  set "SCRIPT=apply_export_preview_and_inputs.py"
)

if exist "%SCRIPT%" (
  echo Running codemod: %SCRIPT% >> "%LOG%"
  "%PYEXE%" "%SCRIPT%" . --write 1>>"%LOG%" 2>&1
  if errorlevel 1 (
    echo [ERROR] Codemod failed; see run.log >> "%LOG%"
    echo.
    echo Codemod failed. See run.log for details.
    echo Press any key to continue to attempt launch anyway...
    pause >nul
  ) else (
    echo Codemod completed. >> "%LOG%"
  )
) else (
  echo [WARN] No codemod script found; skipping update >> "%LOG%"
)

REM --- Verify entry file exists ---
if not exist "Home.py" (
  echo [ERROR] Home.py not found in %CD% >> "%LOG%"
  echo.
  echo Home.py not found in %CD%.
  echo If your entry file is different, edit this BAT file and change "Home.py".
  echo Press any key to exit...
  pause >nul
  exit /b 1
)

REM --- Launch Streamlit in THIS window so errors remain visible ---
echo Launching: streamlit run Home.py >> "%LOG%"
echo.
"%PYEXE%" -m streamlit run "Home.py" --server.port 8501 1>>"%LOG%" 2>&1

REM If Streamlit exits, pause so you can read any error
echo.
echo Streamlit exited (or was closed). See run.log for details.
echo Press any key to exit...
pause >nul
exit /b 0
