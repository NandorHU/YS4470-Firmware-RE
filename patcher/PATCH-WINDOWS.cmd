@echo off
setlocal
set "PATCH_EXIT=0"
if "%~1"=="" (
  echo Drag your original f1c100s.bin or 16 MiB backup onto this file.
  echo Creates a NEW continuous 1.0 file. Never connects to the meter.
  goto finish
)
py -3 --version >nul 2>nul
if errorlevel 1 goto use_python
py -3 "%~dp0ys4470_patch.py" apply "%~1" --variant continuous --output "%~dpn1-ys4470-1.0-continuous.bin"
goto result
:use_python
python --version >nul 2>nul
if errorlevel 1 goto no_python
python "%~dp0ys4470_patch.py" apply "%~1" --variant continuous --output "%~dpn1-ys4470-1.0-continuous.bin"
:result
set "PATCH_EXIT=%ERRORLEVEL%"
goto finish
:no_python
echo Python 3.10 or newer is required. Install it with the PATH option enabled.
set "PATCH_EXIT=2"
:finish
if not defined YS4470_NO_PAUSE pause
exit /b %PATCH_EXIT%
