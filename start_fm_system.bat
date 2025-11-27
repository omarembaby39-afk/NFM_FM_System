@echo off
cd /d "%~dp0"

echo Starting Nile Facility Management System on localhost:8501 ...
echo.

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Run Streamlit app on localhost only
streamlit run app.py --server.address=localhost --server.port=8501

echo.
echo App closed. Press any key to exit.
pause >nul
