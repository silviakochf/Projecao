@echo off
:: Script de automação para configuração e execução do ambiente Paestro

if not exist venv (
    echo [INFO] Criando ambiente virtual Python...
    python -m venv venv
)

echo [INFO] Ativando ambiente virtual...
call venv\Scripts\activate

echo [INFO] Verificando e instalando dependencias...
:: Garante a instalação do gerenciador de variáveis de ambiente
pip install python-dotenv
pip install -r requirements.txt

echo [INFO] Iniciando servidor Flask...
start "" "http://127.0.0.1:5000"

:: Executa o ponto de entrada principal na raiz
python run.py

pause