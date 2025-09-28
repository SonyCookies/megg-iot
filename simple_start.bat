@echo off
echo Starting MEGG IoT Backend (Simple WebSocket API)...
echo ========================================================

REM Install dependencies if needed
python -m pip install -r requirements.txt

REM Start the simple IoT backend server
python simple_main.py

pause

