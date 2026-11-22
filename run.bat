@echo off
rem Start (Windows): input\ -> output\.  run.bat --web: podglad w przegladarce http://localhost:8000
rem Python: .venv\Scripts\python.exe, potem "py -3", potem "python" z PATH. Klucz modelu w .env czyta sam program.
setlocal
pushd "%~dp0"
set "PYTHONPATH=%CD%\src"
set "PYTHONUTF8=1"
set "PY="
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"
if not defined PY (py -3 --version >nul 2>&1 && set "PY=py -3")
if not defined PY set "PY=python"
if not defined TESSDATA_PREFIX if exist ".cache\tessdata\pol.traineddata" set "TESSDATA_PREFIX=%CD%\.cache\tessdata"
if /i "%~1"=="--web" (
  %PY% -m odwolania2json.web
) else (
  %PY% -m odwolania2json --input "%CD%\input" --output "%CD%\output" %*
)
set "KOD=%ERRORLEVEL%"
popd
endlocal & exit /b %KOD%
