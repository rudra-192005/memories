@echo off
echo ================================
echo Starting Private Memory Site
echo ================================

REM Check Python version
python --version 2>NUL | find "3." >NUL
if errorlevel 1 (
    echo ❌ Python 3.x is required
    pause
    exit /b 1
)

echo ✅ Python found

REM Create virtual environment if not exists
if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Install requirements
echo Installing requirements...
pip install -r requirements.txt

REM Initialize database if not exists
if not exist memories.db (
    echo Initializing database...
    python init_db.py
)

REM Start the application
echo Starting server...
echo Access your memory site at: http://localhost:5000
echo ================================

set FLASK_APP=app.py
set FLASK_ENV=development
set FLASK_DEBUG=1

python app.py
pause
