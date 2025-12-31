@echo off
set GEMINI_MODEL=gemini-2.0-flash
cd /d D:\OryggiAI_Service\Advance_Chatbot
.\venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 9000
