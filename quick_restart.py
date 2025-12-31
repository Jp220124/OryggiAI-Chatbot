"""Quick restart without psutil"""
import subprocess
import time
import os

PORT = 9000

# Find and kill processes on port
print("Finding processes on port 9000...")
result = subprocess.run("netstat -ano | findstr :9000 | findstr LISTENING",
                       shell=True, capture_output=True, text=True)
if result.stdout:
    for line in result.stdout.strip().split('\n'):
        parts = line.split()
        if len(parts) >= 5:
            pid = parts[-1]
            print(f"Killing PID {pid}...")
            subprocess.run(f"taskkill /F /PID {pid}", shell=True, capture_output=True)
            time.sleep(1)

print("\nWaiting for port to be released...")
time.sleep(2)

# Start new server
print("Starting new server...")
os.chdir(r"D:\OryggiAI_Service\Advance_Chatbot")
subprocess.Popen([
    r"venv\Scripts\python.exe",
    "-m", "uvicorn",
    "app.main:app",
    "--host", "0.0.0.0",
    "--port", str(PORT)
    # NOTE: --reload removed to prevent Windows async event loop conflicts with Google API
])

print(f"Server starting on port {PORT}...")
time.sleep(8)

# Verify
result = subprocess.run("curl -s http://localhost:9000/health", shell=True, capture_output=True, text=True)
print(f"Health check: {result.stdout}")
