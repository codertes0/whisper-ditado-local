@echo off
REM Setup unico: cria venv e instala dependencias
cd /d "%~dp0"

if not exist ".venv" (
    echo [setup] criando venv...
    py -3 -m venv .venv
)

call .venv\Scripts\activate.bat

echo [setup] atualizando pip...
python -m pip install --upgrade pip

echo [setup] instalando dependencias (isso baixa ~1.5GB do Whisper na primeira execucao)...
pip install -r requirements.txt

echo.
echo [setup] OK. Rode "run.bat" pra iniciar.
pause
