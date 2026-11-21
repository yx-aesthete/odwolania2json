@echo off
cd /d "%~dp0"
set PYTHONPATH=%CD%\src
if "%1"=="--web" (python -m odwolania2json.web) else (python -m odwolania2json --input .\input --output .\output %*)
