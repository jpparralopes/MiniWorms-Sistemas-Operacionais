@echo off
setlocal EnableExtensions
cd /d "%~dp0"
echo.
echo Mini Worms - Geracao de entrega compacta
set "CSC=%WINDIR%\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if not exist "%CSC%" set "CSC=%WINDIR%\Microsoft.NET\Framework\v4.0.30319\csc.exe"
if not exist "%CSC%" (
  echo ERRO: compilador C# do .NET Framework nao localizado.
  echo Verifique a instalacao do .NET Framework 4.x.
  pause
  exit /b 1
)
if not exist "MiniWormsLauncher.cs" (
  echo ERRO: MiniWormsLauncher.cs nao encontrado.
  pause
  exit /b 1
)
"%CSC%" /nologo /optimize+ /target:winexe /reference:System.Windows.Forms.dll /out:"MiniWorms.exe" "MiniWormsLauncher.cs"
if errorlevel 1 goto erro
if not exist "MiniWorms.exe" goto erro
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0EMPACOTAR_WINDOWS.ps1"
if errorlevel 1 goto erro
echo.
echo SUCESSO: abra a pasta ENTREGA para pegar os dois ZIPs.
echo TESTE: de dois cliques em MiniWorms.exe nesta pasta.
echo IMPORTANTE: para executar este EXE, e necessario Python 3 instalado.
pause
exit /b 0
:erro
echo.
echo ERRO: nao foi possivel finalizar a geracao.
pause
exit /b 1