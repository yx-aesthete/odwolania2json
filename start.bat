@echo off
rem Start aplikacji (Windows): input\ -> output\. Klucz modelu w pliku .env (wzor: .env.example).
rem start.bat --web  uruchamia podglad w przegladarce: http://localhost:8000
setlocal
call "%~dp0run.bat" %*
set "KOD=%ERRORLEVEL%"
endlocal & exit /b %KOD%
