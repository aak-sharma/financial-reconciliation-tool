@echo off
REM Financial Reconciliation Tool - Windows Quick Start Script

cls
echo ======================================
echo Financial Reconciliation Tool
echo Quick Start Setup (Windows)
echo ======================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python 3.8+ from python.org
    pause
    exit /b 1
)

echo Success: Python found
python --version
echo.

REM Create virtual environment if not exists
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
    echo Success: Virtual environment created
) else (
    echo Success: Virtual environment already exists
)

echo.

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

echo.

REM Install requirements
echo Installing dependencies...
pip install -q -r requirements.txt
if errorlevel 1 (
    echo Error: Failed to install dependencies
    pause
    exit /b 1
)
echo Success: Dependencies installed

echo.

REM Generate sample data
echo Generating sample data...
cd data
python generate_sample_data.py
cd ..

echo.
echo ======================================
echo Setup Complete!
echo ======================================
echo.
echo Starting the application...
echo.
echo The server will run on: http://localhost:5000
echo.
echo Instructions:
echo 1. Wait for Flask to start (you'll see 'Running on...')
echo 2. Open http://localhost:5000 in your browser
echo 3. Sample CSV files are in the 'data' folder
echo 4. Upload the sample files and run reconciliation
echo.
echo Press Ctrl+C to stop the server
echo.

REM Start Flask app
cd backend
python app.py

pause
