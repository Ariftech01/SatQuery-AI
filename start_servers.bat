@echo off
echo ========================================================
echo Starting SatQuery AI (Backend & Frontend)
echo SIH26167 - ISRO Space Technology Remote Sensing Assistant
echo ========================================================

start "SatQuery AI Backend (FastAPI)" cmd /k "cd /d %~dp0backend && python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload"
timeout /t 2 >nul
start "SatQuery AI Frontend (Vite)" cmd /k "cd /d %~dp0frontend && npm run dev -- --host 127.0.0.1 --port 5173"

echo.
echo SatQuery AI is launching!
echo Backend API:  http://127.0.0.1:8000 (Docs: http://127.0.0.1:8000/docs)
echo Frontend UI:  http://127.0.0.1:5173
echo.
