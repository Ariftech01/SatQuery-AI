@echo off
echo Running SatQuery AI Automated Pytest Suite...
cd /d %~dp0
python -m pytest backend/tests/ -v
pause
