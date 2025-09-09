@echo off
cd /d D:\Comet2\Comet
call .venv\Scripts\activate.bat
python -m pip install -r requirements.txt
python main.py
pause
