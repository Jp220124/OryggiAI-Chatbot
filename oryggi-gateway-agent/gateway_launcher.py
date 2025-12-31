"""
OryggiAI Gateway Agent - Universal Launcher

This is a simple GUI launcher that:
1. Reads configuration from gateway-launch-config.json (in same folder)
2. Downloads the main installer from the server
3. Runs the installer with pre-filled parameters
4. Provides a clean, professional installation experience

Build this once with PyInstaller, then distribute with a config file.

Build command:
    pyinstaller --onefile --noconsole --name=OryggiAI-Gateway-Launcher --uac-admin gateway_launcher.py

Usage:
    1. Place OryggiAI-Gateway-Launcher.exe in a folder
    2. Create gateway-launch-config.json with your configuration
    3. Double-click the launcher
"""

import os
import sys
import json
import tempfile
import subprocess
import urllib.request
import ctypes
import tkinter as tk
from tkinter import ttk, messagebox
import threading
from pathlib import Path


# ============================================================================
# Configuration Loading
# ============================================================================

def get_config_path():
    """Get path to config file (same directory as executable)"""
    if getattr(sys, 'frozen', False):
        # Running as compiled exe
        base_dir = Path(sys.executable).parent
    else:
        # Running as script
        base_dir = Path(__file__).parent

    return base_dir / "gateway-launch-config.json"


def load_config():
    """Load configuration from JSON file"""
    config_path = get_config_path()

    default_config = {
        "gateway_token": "",
        "database_name": "",
        "gateway_url": "wss://api.oryggi.ai/api/gateway/ws",
        "db_host": "localhost",
        "db_port": 1433,
        "server_url": "https://api.oryggi.ai",
        "installer_filename": "OryggiAI-Gateway-Setup.exe"
    }

    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                user_config = json.load(f)
                default_config.update(user_config)
        except Exception as e:
            print(f"Warning: Could not load config: {e}")

    return default_config


# ============================================================================
# Admin Rights Check
# ============================================================================

def is_admin():
    """Check if running with administrator privileges"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


def run_as_admin():
    """Re-launch the script with admin privileges"""
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, " ".join(sys.argv), None, 1
    )


# ============================================================================
# Installer Launcher GUI
# ============================================================================

class LauncherApp:
    def __init__(self, config):
        self.config = config
        self.root = tk.Tk()
        self.setup_window()
        self.create_widgets()

    def setup_window(self):
        """Configure the main window"""
        self.root.title("OryggiAI Gateway Agent Setup")
        self.root.geometry("480x220")
        self.root.resizable(False, False)

        # Center window on screen
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f"+{x}+{y}")

        # Style
        style = ttk.Style()
        style.configure("Header.TLabel", font=("Segoe UI", 16, "bold"))
        style.configure("Status.TLabel", font=("Segoe UI", 10))

    def create_widgets(self):
        """Create UI elements"""
        # Main frame with padding
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Header
        header = ttk.Label(
            main_frame,
            text="OryggiAI Gateway Agent",
            style="Header.TLabel"
        )
        header.pack(pady=(0, 5))

        # Subheader
        subheader = ttk.Label(
            main_frame,
            text="Setting up your database connection...",
            foreground="gray"
        )
        subheader.pack(pady=(0, 20))

        # Progress bar
        self.progress = ttk.Progressbar(
            main_frame,
            length=400,
            mode='indeterminate'
        )
        self.progress.pack(pady=10)

        # Status label
        self.status_label = ttk.Label(
            main_frame,
            text="Initializing...",
            style="Status.TLabel"
        )
        self.status_label.pack(pady=10)

        # Info label (shows config summary)
        if self.config.get("database_name"):
            info_text = f"Database: {self.config['database_name']} @ {self.config['db_host']}"
        else:
            info_text = f"Server: {self.config['db_host']}"

        info_label = ttk.Label(
            main_frame,
            text=info_text,
            foreground="darkblue"
        )
        info_label.pack(pady=(5, 0))

    def update_status(self, text):
        """Update the status label (thread-safe)"""
        self.root.after(0, lambda: self.status_label.config(text=text))

    def show_error(self, title, message):
        """Show error dialog and close"""
        self.root.after(0, lambda: messagebox.showerror(title, message))
        self.root.after(100, self.root.destroy)

    def close(self):
        """Close the launcher window"""
        self.root.after(0, self.root.destroy)

    def run_installation(self):
        """Main installation logic (runs in background thread)"""
        try:
            # Step 1: Prepare download URL
            self.update_status("Preparing download...")

            server_url = self.config.get("server_url", "https://api.oryggi.ai")

            # Try Inno Setup installer first, fall back to GUI agent exe
            installer_url = f"{server_url}/api/gateway/download-installer-exe"
            fallback_url = f"{server_url}/api/gateway/download-agent-exe"

            # Step 2: Download installer
            self.update_status("Downloading installer...")

            temp_dir = tempfile.gettempdir()
            installer_path = os.path.join(temp_dir, self.config.get("installer_filename", "OryggiAI-Gateway-Setup.exe"))

            downloaded = False
            try:
                # Try Inno Setup installer first
                urllib.request.urlretrieve(installer_url, installer_path)
                # Check if it's a valid PE file (not error JSON)
                with open(installer_path, 'rb') as f:
                    header = f.read(2)
                    if header == b'MZ':  # Valid PE file
                        downloaded = True
            except:
                pass

            if not downloaded:
                # Fall back to GUI agent exe
                self.update_status("Downloading agent application...")
                try:
                    installer_path = os.path.join(temp_dir, "OryggiAI-Gateway.exe")
                    urllib.request.urlretrieve(fallback_url, installer_path)
                    downloaded = True
                except urllib.error.URLError as e:
                    self.show_error("Download Error", f"Failed to download agent:\n{str(e)}")
                    return
                except Exception as e:
                    self.show_error("Download Error", f"Unexpected error during download:\n{str(e)}")
                    return

            # Step 3: Save configuration file for the agent
            self.update_status("Saving configuration...")

            # Create config in same directory as downloaded exe
            config_path = os.path.join(temp_dir, "gateway-config.json")
            config_data = {
                "gateway_token": self.config.get("gateway_token", ""),
                "gateway_url": self.config.get("gateway_url", ""),
                "db_host": self.config.get("db_host", "localhost"),
                "db_port": self.config.get("db_port", 1433),
                "db_database": self.config.get("database_name", ""),
                "db_trusted_connection": True
            }
            with open(config_path, 'w') as f:
                json.dump(config_data, f, indent=2)

            # Step 4: Build command line arguments
            self.update_status("Preparing installation...")

            args = [installer_path]

            # Add token if available
            token = self.config.get("gateway_token", "")
            if token:
                args.append(f"--token={token}")

            # Add database if specified
            database = self.config.get("database_name", "")
            if database:
                args.append(f"--database={database}")

            # Add server details
            args.append(f"--db-host={self.config.get('db_host', 'localhost')}")
            args.append(f"--db-port={self.config.get('db_port', 1433)}")

            # Add gateway URL
            gateway_url = self.config.get("gateway_url", "")
            if gateway_url:
                args.append(f"--gateway-url={gateway_url}")

            # Step 5: Launch installer/agent
            self.update_status("Starting Gateway Agent...")

            try:
                # Run the installer/agent
                process = subprocess.Popen(args)

                # Close our launcher - the agent takes over
                self.close()

            except Exception as e:
                self.show_error("Launch Error", f"Failed to start agent:\n{str(e)}")
                return

        except Exception as e:
            self.show_error("Error", f"Unexpected error:\n{str(e)}")

    def start(self):
        """Start the launcher"""
        # Validate configuration
        if not self.config.get("gateway_token"):
            # No token - show warning but continue (installer will ask)
            pass

        # Start progress animation
        self.progress.start(10)

        # Run installation in background thread
        thread = threading.Thread(target=self.run_installation, daemon=True)
        thread.start()

        # Start main loop
        self.root.mainloop()


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    """Main entry point"""
    # Check for admin rights
    if not is_admin():
        # Show brief message and re-launch as admin
        print("Requesting administrator privileges...")
        run_as_admin()
        sys.exit(0)

    # Load configuration
    config = load_config()

    # Validate minimum config
    if not config.get("server_url"):
        messagebox.showerror(
            "Configuration Error",
            "Missing server_url in configuration.\n\n"
            "Please ensure gateway-launch-config.json exists and contains valid configuration."
        )
        sys.exit(1)

    # Run the launcher
    app = LauncherApp(config)
    app.start()


if __name__ == "__main__":
    main()
