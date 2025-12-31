"""
Restart Server Script
Kills existing server on port 9000 and starts fresh with updated config
"""
import os
import signal
import subprocess
import time
import psutil

def kill_server_on_port(port):
    """Kill any process listening on the specified port"""
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            # Get connections separately
            connections = proc.net_connections()
            if connections:
                for conn in connections:
                    if hasattr(conn, 'laddr') and conn.laddr.port == port:
                        print(f"Killing process {proc.info['pid']} ({proc.info['name']}) on port {port}")
                        proc.kill()
                        proc.wait(timeout=3)
                        return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return False

def main():
    PORT = 9000

    print("=" * 80)
    print("SERVER RESTART SCRIPT")
    print("=" * 80)

    # Step 1: Kill existing server
    print(f"\n[1] Checking for server on port {PORT}...")
    if kill_server_on_port(PORT):
        print(f"✓ Server on port {PORT} killed successfully")
        time.sleep(2)  # Wait for port to be released
    else:
        print(f"No server found on port {PORT}")

    # Step 2: Start new server
    print(f"\n[2] Starting new server on port {PORT}...")
    os.chdir(os.path.dirname(__file__))

    # Start server in background
    cmd = [
        "venv/Scripts/python.exe",
        "-m", "uvicorn",
        "app.main:app",
        "--host", "0.0.0.0",
        "--port", str(PORT)
    ]

    subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    print(f"✓ Server started on port {PORT}")
    print(f"\nServer is now running with updated configuration!")
    print(f"Access Swagger UI at: http://localhost:{PORT}/docs")
    print("\nPress Ctrl+C to stop this script (server will continue running)")

    # Keep script running for a few seconds to show status
    time.sleep(5)

if __name__ == "__main__":
    main()
