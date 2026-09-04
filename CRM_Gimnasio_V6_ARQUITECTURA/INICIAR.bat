@echo off
setlocal
cd /d "%~dp0"
title Fight Gym CRM

echo ============================================
echo        FIGHT GYM CRM - INICIO
echo ============================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [1/4] Creando entorno virtual...
    py -m venv .venv
    if errorlevel 1 (
        echo.
        echo ERROR: No se pudo crear el entorno virtual.
        echo Comprueba que Python este instalado y que el comando "py" funciona.
        pause
        exit /b 1
    )
) else (
    echo [1/4] Entorno virtual encontrado.
)

echo [2/4] Actualizando pip...
".venv\Scripts\python.exe" -m pip install --upgrade pip

echo.
echo [3/4] Instalando/verificando dependencias...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo ERROR: Fallo instalando dependencias.
    echo Ejecuta DIAGNOSTICO.bat y enviame el resultado.
    pause
    exit /b 1
)

echo.
echo [4/4] Comprobando PySide6, pandas y matplotlib...
".venv\Scripts\python.exe" -c "import PySide6, pandas, matplotlib; print('Dependencias OK')"
if errorlevel 1 (
    echo.
    echo ERROR: Las dependencias no estan disponibles en el entorno virtual.
    pause
    exit /b 1
)

echo.
echo Iniciando Fight Gym CRM...
echo.
".venv\Scripts\python.exe" main.py 2> error_inicio.txt

if errorlevel 1 (
    echo.
    echo ============================================
    echo EL PROGRAMA HA DADO UN ERROR
    echo ============================================
    type error_inicio.txt
    echo.
    echo Tambien se ha guardado en: error_inicio.txt
    pause
    exit /b 1
)

endlocal
