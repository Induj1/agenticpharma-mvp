@echo off
echo ============================================================
echo  AgenticPharma MVP - Local Startup
echo ============================================================

echo.
echo [1/4] Starting MongoDB via Docker...
docker compose up -d
timeout /t 3 /nobreak > nul

echo.
echo [2/4] Installing Python dependencies...
pip install -r requirements.txt -q

echo.
echo [3/4] Loading CSVs into MongoDB...
python ingestion\load_csvs.py

echo.
echo [4/4] Starting Streamlit app...
echo   Open: http://localhost:8501
echo.
streamlit run app\main.py
