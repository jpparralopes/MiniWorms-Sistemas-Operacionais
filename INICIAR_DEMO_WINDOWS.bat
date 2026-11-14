@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if not errorlevel 1 (
  set "CMDPY=py -3"
) else (
  set "CMDPY=python"
)
start "Mini Worms - Servidor" cmd /k "%CMDPY% servidor.py"
timeout /t 2 /nobreak >nul
start "Mini Worms - Jogador 1" cmd /c "%CMDPY% cliente.py"
start "Mini Worms - Jogador 2" cmd /c "%CMDPY% cliente.py"
echo Servidor e dois clientes iniciados.
exit /b 0