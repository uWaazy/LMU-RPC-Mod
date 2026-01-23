@echo off
echo Iniciando LMU RPC Mod...
".\.venv\Scripts\python.exe" lmu_rpc.py
if %errorlevel% neq 0 (
    echo.
    echo ERRO CRITICO: Nao foi possivel iniciar.
    echo Verifique se a pasta .venv existe.
    pause
)