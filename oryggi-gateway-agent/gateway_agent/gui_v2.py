"""
OryggiAI Gateway Agent - Zero-Config GUI Application v2.0

A user-friendly graphical interface that requires ZERO SQL Server configuration.
- Uses Windows Authentication by default (no password needed!)
- Auto-discovers local SQL Server databases
- Pre-fills token from command line or config
- Runs as Windows Service for auto-start
"""

import asyncio
import threading
import logging
import sys
import os
import ctypes
from typing import Optional, List
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

import pyodbc

# Import agent components - support both package and standalone/frozen modes
try:
    # When running as part of package (e.g., python -m gateway_agent.gui_v2)
    from .config import AgentConfig, DatabaseConfig, GatewayConfig, LoggingConfig
    from .database import LocalDatabaseManager
    from .connection import GatewayConnection
    from .api_client import LocalApiClient
    from .api_discovery import discover_oryggi_api
except ImportError:
    try:
        # When running as frozen exe (PyInstaller) - modules are under gateway_agent
        from gateway_agent.config import AgentConfig, DatabaseConfig, GatewayConfig, LoggingConfig
        from gateway_agent.database import LocalDatabaseManager
        from gateway_agent.connection import GatewayConnection
        from gateway_agent.api_client import LocalApiClient
        from gateway_agent.api_discovery import discover_oryggi_api
    except ImportError:
        # When running as standalone script in same directory
        from config import AgentConfig, DatabaseConfig, GatewayConfig, LoggingConfig
        from database import LocalDatabaseManager
        from connection import GatewayConnection
        from api_client import LocalApiClient
        from api_discovery import discover_oryggi_api


class GatewayAgentGUI:
    """
    Zero-Config Graphical User Interface for OryggiAI Gateway Agent

    Key Features:
    - Auto-discovers local SQL Server instances and databases
    - Uses Windows Authentication by default (no password needed!)
    - Pre-fills gateway token from URL/command line
    - One-click connection
    - System tray support for background operation
    """

    def __init__(self, token: str = None, saas_url: str = None, database: str = None):
        # Set DPI awareness BEFORE creating window
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-monitor DPI aware
        except:
            pass

        self.root = tk.Tk()
        self.root.title("OryggiAI Gateway Agent")
        self.root.geometry("600x800")  # Larger to fit all content
        self.root.resizable(True, True)  # Allow resizing

        # Pre-filled values from installer/URL
        self.prefilled_token = token
        self.prefilled_saas_url = saas_url or "ws://103.197.77.163:3000/api/gateway/ws"
        self.prefilled_database = database

        # Set icon if available
        try:
            icon_path = os.path.join(os.path.dirname(__file__), "icon.ico")
            if os.path.exists(icon_path):
                self.root.iconbitmap(icon_path)
        except:
            pass

        # Configure colors (modern dark theme)
        self.bg_color = "#1a1a2e"
        self.card_color = "#16213e"
        self.accent_color = "#667eea"
        self.text_color = "#ffffff"
        self.secondary_text = "#a0aec0"
        self.success_color = "#48bb78"
        self.error_color = "#fc8181"
        self.warning_color = "#ecc94b"

        self.root.configure(bg=self.bg_color)

        # Variables
        self.gateway_token = tk.StringVar(value=self.prefilled_token or "")
        self.saas_url = tk.StringVar(value=self.prefilled_saas_url)
        self.selected_server = tk.StringVar(value="localhost")
        self.selected_database = tk.StringVar()
        self.use_windows_auth = tk.BooleanVar(value=True)  # Default to Windows Auth!
        self.db_username = tk.StringVar()
        self.db_password = tk.StringVar()
        self.install_service = tk.BooleanVar(value=True)

        # Available databases (populated by discovery)
        self.discovered_servers: List[str] = []
        self.discovered_databases: List[str] = []

        # Agent state
        self.agent = None
        self.agent_thread = None
        self.connected = False

        # Setup logging to GUI
        self.setup_logging()

        # Build UI
        self.create_widgets()

        # Center window
        self.center_window()

        # Auto-discover databases on startup
        self.root.after(500, self.discover_databases)

    def setup_logging(self):
        """Configure logging to display in GUI"""
        self.log_handler = GUILogHandler(self)
        logging.getLogger("gateway_agent").addHandler(self.log_handler)
        logging.getLogger("gateway_agent").setLevel(logging.INFO)

    def center_window(self):
        """Center the window on screen"""
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')

    def create_widgets(self):
        """Build the GUI components"""
        # Main container with scrollable frame
        main_frame = tk.Frame(self.root, bg=self.bg_color)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Header
        header_frame = tk.Frame(main_frame, bg=self.bg_color)
        header_frame.pack(fill=tk.X, pady=(0, 15))

        title_label = tk.Label(
            header_frame,
            text="OryggiAI Gateway Agent",
            font=("Segoe UI", 20, "bold"),
            fg=self.text_color,
            bg=self.bg_color
        )
        title_label.pack()

        subtitle_label = tk.Label(
            header_frame,
            text="Connect your database to OryggiAI in one click!",
            font=("Segoe UI", 10),
            fg=self.secondary_text,
            bg=self.bg_color
        )
        subtitle_label.pack()

        # Step 1: Gateway Token
        self.create_step_header(main_frame, "1", "Gateway Token")
        token_frame = self.create_card(main_frame)

        if self.prefilled_token:
            # Token is pre-filled, show it as read-only
            token_display = tk.Label(
                token_frame,
                text=f"Token: {self.prefilled_token[:20]}...",
                font=("Segoe UI", 10),
                fg=self.success_color,
                bg=self.card_color
            )
            token_display.pack(fill=tk.X, padx=10, pady=10)

            check_label = tk.Label(
                token_frame,
                text="✓ Token pre-configured from installer",
                font=("Segoe UI", 9),
                fg=self.success_color,
                bg=self.card_color
            )
            check_label.pack(anchor=tk.W, padx=10, pady=(0, 10))
        else:
            self.create_entry(token_frame, "Paste your token from the dashboard:", self.gateway_token, show="")

        # Step 2: Select Database
        self.create_step_header(main_frame, "2", "Select Your Database")
        db_frame = self.create_card(main_frame)

        # Server selection
        server_label = tk.Label(
            db_frame,
            text="SQL Server Instance:",
            font=("Segoe UI", 9),
            fg=self.secondary_text,
            bg=self.card_color,
            anchor=tk.W
        )
        server_label.pack(fill=tk.X, padx=10, pady=(10, 2))

        server_row = tk.Frame(db_frame, bg=self.card_color)
        server_row.pack(fill=tk.X, padx=10, pady=(0, 10))

        self.server_combo = ttk.Combobox(
            server_row,
            textvariable=self.selected_server,
            values=["localhost", "localhost\\SQLEXPRESS", ".\\SQLEXPRESS"],
            font=("Segoe UI", 10),
            state="normal"
        )
        self.server_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.server_combo.bind("<<ComboboxSelected>>", lambda e: self.discover_databases())
        self.server_combo.bind("<Return>", lambda e: self.discover_databases())

        refresh_btn = tk.Button(
            server_row,
            text="Refresh",
            font=("Segoe UI", 9),
            command=self.discover_databases,
            cursor="hand2"
        )
        refresh_btn.pack(side=tk.RIGHT, padx=(10, 0))

        # Database dropdown
        db_label = tk.Label(
            db_frame,
            text="Database:",
            font=("Segoe UI", 9),
            fg=self.secondary_text,
            bg=self.card_color,
            anchor=tk.W
        )
        db_label.pack(fill=tk.X, padx=10, pady=(5, 2))

        self.db_combo = ttk.Combobox(
            db_frame,
            textvariable=self.selected_database,
            values=[],
            font=("Segoe UI", 10),
            state="readonly"
        )
        self.db_combo.pack(fill=tk.X, padx=10, pady=(0, 10))

        # Discovery status
        self.discovery_status = tk.Label(
            db_frame,
            text="Discovering databases...",
            font=("Segoe UI", 9),
            fg=self.secondary_text,
            bg=self.card_color
        )
        self.discovery_status.pack(fill=tk.X, padx=10, pady=(0, 10))

        # Step 3: Authentication (collapsed by default since Windows Auth is default)
        self.create_step_header(main_frame, "3", "Authentication (Optional)")
        auth_frame = self.create_card(main_frame)

        # Windows Auth checkbox (checked by default)
        self.auth_check = tk.Checkbutton(
            auth_frame,
            text="Use Windows Authentication (Recommended - No password needed!)",
            variable=self.use_windows_auth,
            font=("Segoe UI", 10),
            fg=self.success_color,
            bg=self.card_color,
            selectcolor=self.bg_color,
            activebackground=self.card_color,
            activeforeground=self.text_color,
            command=self.toggle_auth_fields
        )
        self.auth_check.pack(anchor=tk.W, padx=10, pady=10)

        # SQL Auth fields (hidden by default)
        self.sql_auth_frame = tk.Frame(auth_frame, bg=self.card_color)

        user_label = tk.Label(
            self.sql_auth_frame,
            text="Username:",
            font=("Segoe UI", 9),
            fg=self.secondary_text,
            bg=self.card_color
        )
        user_label.pack(fill=tk.X, padx=10, pady=(5, 2))

        self.user_entry = tk.Entry(
            self.sql_auth_frame,
            textvariable=self.db_username,
            font=("Segoe UI", 10),
            bg="#0f0f23",
            fg=self.text_color,
            insertbackground=self.text_color,
            relief=tk.FLAT
        )
        self.user_entry.pack(fill=tk.X, padx=10, pady=(0, 5))

        pass_label = tk.Label(
            self.sql_auth_frame,
            text="Password:",
            font=("Segoe UI", 9),
            fg=self.secondary_text,
            bg=self.card_color
        )
        pass_label.pack(fill=tk.X, padx=10, pady=(5, 2))

        self.pass_entry = tk.Entry(
            self.sql_auth_frame,
            textvariable=self.db_password,
            font=("Segoe UI", 10),
            bg="#0f0f23",
            fg=self.text_color,
            insertbackground=self.text_color,
            relief=tk.FLAT,
            show="*"
        )
        self.pass_entry.pack(fill=tk.X, padx=10, pady=(0, 10))

        # Service installation option
        service_frame = tk.Frame(main_frame, bg=self.bg_color)
        service_frame.pack(fill=tk.X, pady=10)

        self.service_check = tk.Checkbutton(
            service_frame,
            text="Start automatically with Windows (Recommended)",
            variable=self.install_service,
            font=("Segoe UI", 10),
            fg=self.text_color,
            bg=self.bg_color,
            selectcolor=self.card_color,
            activebackground=self.bg_color,
            activeforeground=self.text_color
        )
        self.service_check.pack(anchor=tk.W)

        # Connect Button (big and prominent)
        button_frame = tk.Frame(main_frame, bg=self.bg_color)
        button_frame.pack(fill=tk.X, pady=15)

        self.connect_btn = tk.Button(
            button_frame,
            text="Connect to OryggiAI",
            font=("Segoe UI", 12, "bold"),
            fg=self.text_color,
            bg=self.accent_color,
            activebackground="#5a67d8",
            activeforeground=self.text_color,
            relief=tk.FLAT,
            cursor="hand2",
            command=self.connect,
            height=2
        )
        self.connect_btn.pack(fill=tk.X)

        # Status indicator
        self.status_frame = tk.Frame(main_frame, bg=self.bg_color)
        self.status_frame.pack(fill=tk.X, pady=5)

        self.status_dot = tk.Canvas(
            self.status_frame,
            width=12,
            height=12,
            bg=self.bg_color,
            highlightthickness=0
        )
        self.status_dot.pack(side=tk.LEFT, padx=(0, 5))
        self.status_dot.create_oval(2, 2, 10, 10, fill="#6b7280", outline="")

        self.status_label = tk.Label(
            self.status_frame,
            text="Not connected",
            font=("Segoe UI", 10),
            fg=self.secondary_text,
            bg=self.bg_color
        )
        self.status_label.pack(side=tk.LEFT)

        # Log Section
        log_label = tk.Label(
            main_frame,
            text="Activity Log",
            font=("Segoe UI", 10, "bold"),
            fg=self.secondary_text,
            bg=self.bg_color,
            anchor=tk.W
        )
        log_label.pack(fill=tk.X, pady=(10, 5))

        # Log text area
        self.log_text = scrolledtext.ScrolledText(
            main_frame,
            height=6,
            font=("Consolas", 9),
            bg=self.card_color,
            fg=self.secondary_text,
            insertbackground=self.text_color,
            relief=tk.FLAT,
            state=tk.DISABLED
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # Configure log tags
        self.log_text.tag_config("info", foreground=self.secondary_text)
        self.log_text.tag_config("success", foreground=self.success_color)
        self.log_text.tag_config("error", foreground=self.error_color)
        self.log_text.tag_config("warning", foreground=self.warning_color)

    def create_step_header(self, parent, number, title):
        """Create a step header with number badge"""
        frame = tk.Frame(parent, bg=self.bg_color)
        frame.pack(fill=tk.X, pady=(15, 5))

        # Number badge
        badge = tk.Label(
            frame,
            text=number,
            font=("Segoe UI", 10, "bold"),
            fg=self.text_color,
            bg=self.accent_color,
            width=3,
            height=1
        )
        badge.pack(side=tk.LEFT, padx=(0, 10))

        # Title
        title_label = tk.Label(
            frame,
            text=title,
            font=("Segoe UI", 11, "bold"),
            fg=self.text_color,
            bg=self.bg_color
        )
        title_label.pack(side=tk.LEFT)

    def create_card(self, parent):
        """Create a styled card frame"""
        frame = tk.Frame(parent, bg=self.card_color)
        frame.pack(fill=tk.X, pady=(0, 5))
        return frame

    def create_entry(self, parent, label_text, variable, show=""):
        """Create a styled label and entry pair"""
        label = tk.Label(
            parent,
            text=label_text,
            font=("Segoe UI", 9),
            fg=self.secondary_text,
            bg=self.card_color,
            anchor=tk.W
        )
        label.pack(fill=tk.X, padx=10, pady=(10, 2))

        entry = tk.Entry(
            parent,
            textvariable=variable,
            font=("Segoe UI", 10),
            bg="#0f0f23",
            fg=self.text_color,
            insertbackground=self.text_color,
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground="#2d3748",
            highlightcolor=self.accent_color,
            show=show
        )
        entry.pack(fill=tk.X, padx=10, pady=(0, 10))
        return entry

    def toggle_auth_fields(self):
        """Show/hide SQL Auth fields based on Windows Auth selection"""
        if self.use_windows_auth.get():
            self.sql_auth_frame.pack_forget()
        else:
            self.sql_auth_frame.pack(fill=tk.X, pady=(0, 10))

    def discover_databases(self):
        """Auto-discover SQL Server databases using Windows Authentication"""
        self.discovery_status.configure(text="Discovering databases...", fg=self.secondary_text)
        self.root.update()

        def do_discovery():
            databases = []
            server = self.selected_server.get().strip()

            try:
                # Try different ODBC drivers
                drivers = [
                    "ODBC Driver 18 for SQL Server",
                    "ODBC Driver 17 for SQL Server",
                    "SQL Server Native Client 11.0",
                    "SQL Server"
                ]

                conn = None
                used_driver = None

                for driver in drivers:
                    try:
                        conn_str = (
                            f"Driver={{{driver}}};"
                            f"Server={server};"
                            "Database=master;"
                            "Trusted_Connection=yes;"
                            "TrustServerCertificate=yes;"
                            "Connection Timeout=5;"
                        )
                        conn = pyodbc.connect(conn_str, timeout=5)
                        used_driver = driver
                        break
                    except:
                        continue

                if conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT name FROM sys.databases
                        WHERE name NOT IN ('master', 'tempdb', 'model', 'msdb')
                        AND state_desc = 'ONLINE'
                        ORDER BY name
                    """)
                    databases = [row[0] for row in cursor.fetchall()]
                    conn.close()

                    self.root.after(0, lambda: self._discovery_complete(databases, used_driver))
                else:
                    self.root.after(0, lambda: self._discovery_failed("No ODBC driver found"))

            except Exception as e:
                self.root.after(0, lambda: self._discovery_failed(str(e)))

        thread = threading.Thread(target=do_discovery, daemon=True)
        thread.start()

    def _discovery_complete(self, databases: List[str], driver: str):
        """Handle successful database discovery"""
        self.discovered_databases = databases
        self.db_combo['values'] = databases

        if databases:
            # Auto-select prefilled database or first one
            if self.prefilled_database and self.prefilled_database in databases:
                self.selected_database.set(self.prefilled_database)
            else:
                self.selected_database.set(databases[0])

            self.discovery_status.configure(
                text=f"✓ Found {len(databases)} database(s) using Windows Authentication",
                fg=self.success_color
            )
            self.log_message(f"Discovered {len(databases)} databases using {driver}", "success")
        else:
            self.discovery_status.configure(
                text="No databases found. Check SQL Server is running.",
                fg=self.warning_color
            )

    def _discovery_failed(self, error: str):
        """Handle database discovery failure"""
        self.discovery_status.configure(
            text=f"Could not connect: {error[:50]}...",
            fg=self.error_color
        )
        self.log_message(f"Database discovery failed: {error}", "error")

        # Suggest checking SQL Server
        if "Login failed" in error or "Cannot open database" in error:
            self.log_message("Tip: Make sure SQL Server is running", "warning")
        elif "TCP/IP" in error or "connection" in error.lower():
            self.log_message("Tip: Check SQL Server is accepting connections", "warning")

    def log_message(self, message, level="info"):
        """Add a message to the log display"""
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n", level)
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def update_status(self, connected, message=""):
        """Update the connection status indicator"""
        self.connected = connected

        if connected:
            self.status_dot.itemconfig(1, fill=self.success_color)
            self.status_label.configure(text="Connected to OryggiAI", fg=self.success_color)
            self.connect_btn.configure(text="Disconnect", bg=self.error_color)
        else:
            self.status_dot.itemconfig(1, fill="#6b7280")
            status_text = message if message else "Not connected"
            self.status_label.configure(text=status_text, fg=self.secondary_text)
            self.connect_btn.configure(text="Connect to OryggiAI", bg=self.accent_color)

    def validate_inputs(self) -> bool:
        """Validate all input fields"""
        token = self.gateway_token.get().strip()
        if not token:
            messagebox.showerror("Error", "Gateway token is required!\n\nGet your token from the OryggiAI dashboard.")
            return False

        if not token.startswith("gw_"):
            messagebox.showerror("Error", "Invalid gateway token format.\n\nToken should start with 'gw_'")
            return False

        if not self.selected_database.get():
            messagebox.showerror("Error", "Please select a database!")
            return False

        if not self.use_windows_auth.get():
            if not self.db_username.get().strip():
                messagebox.showerror("Error", "Username is required for SQL Authentication!")
                return False

        return True

    def get_config(self) -> AgentConfig:
        """Build configuration from GUI inputs"""
        db_config = DatabaseConfig(
            host=self.selected_server.get().strip(),
            port=1433,
            database=self.selected_database.get().strip(),
            username=self.db_username.get().strip() if not self.use_windows_auth.get() else "",
            password=self.db_password.get().strip() if not self.use_windows_auth.get() else "",
            use_windows_auth=self.use_windows_auth.get(),
            driver="ODBC Driver 17 for SQL Server",  # Will be auto-detected
        )

        gateway_config = GatewayConfig(
            gateway_token=self.gateway_token.get().strip(),
            saas_url=self.saas_url.get().strip(),
        )

        logging_config = LoggingConfig(
            level="INFO",
            file=None,
        )

        return AgentConfig(
            database=db_config,
            gateway=gateway_config,
            logging=logging_config,
        )

    def connect(self):
        """Start the gateway connection"""
        if self.connected:
            self.disconnect()
            return

        if not self.validate_inputs():
            return

        self.log_message("Starting gateway connection...", "info")
        self.connect_btn.configure(state=tk.DISABLED, text="Connecting...")

        def run_agent():
            try:
                config = self.get_config()

                # Auto-detect ODBC driver
                drivers = [
                    "ODBC Driver 18 for SQL Server",
                    "ODBC Driver 17 for SQL Server",
                    "SQL Server Native Client 11.0",
                ]
                for driver in drivers:
                    try:
                        test_str = f"Driver={{{driver}}};Server=localhost;Database=master;Trusted_Connection=yes;TrustServerCertificate=yes;"
                        pyodbc.connect(test_str, timeout=2)
                        config.database.driver = driver
                        break
                    except:
                        continue

                # Test database first
                database = LocalDatabaseManager(config.database)
                db_result = database.test_connection()

                if not db_result["success"]:
                    self.root.after(0, lambda: self._connection_failed(
                        f"Database connection failed: {db_result.get('error')}"
                    ))
                    return

                self.root.after(0, lambda: self.log_message(
                    f"Connected to {config.database.database}", "success"
                ))

                # Initialize API client (auto-discover local Oryggi API)
                api_client = None
                try:
                    api_url = discover_oryggi_api()
                    if api_url:
                        # Disable SSL verification for localhost (self-signed certs)
                        is_localhost = "localhost" in api_url.lower() or "127.0.0.1" in api_url
                        api_client = LocalApiClient(api_url, verify_ssl=not is_localhost)
                        self.root.after(0, lambda: self.log_message(
                            f"[API] Connected to Oryggi API: {api_url} (SSL verify: {not is_localhost})", "success"
                        ))
                except Exception as e:
                    self.root.after(0, lambda: self.log_message(
                        f"[API] No local Oryggi API found", "info"
                    ))

                # Create connection with API client
                connection = GatewayConnection(config.gateway, database, api_client=api_client)

                # Run the connection
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                self.root.after(0, lambda: self._connection_started())

                try:
                    loop.run_until_complete(connection.run())
                finally:
                    loop.close()

                self.root.after(0, lambda: self._connection_ended())

            except Exception as e:
                self.root.after(0, lambda: self._connection_failed(str(e)))

        self.agent_thread = threading.Thread(target=run_agent, daemon=True)
        self.agent_thread.start()

    def _connection_started(self):
        """Handle successful connection start"""
        self.update_status(True)
        self.connect_btn.configure(state=tk.NORMAL)
        self.log_message("Connected to OryggiAI!", "success")
        self.log_message("Your database is now accessible from the OryggiAI chat.", "info")

    def _connection_failed(self, error: str):
        """Handle connection failure"""
        self.update_status(False, "Connection failed")
        self.connect_btn.configure(state=tk.NORMAL)
        self.log_message(f"Connection failed: {error}", "error")
        messagebox.showerror("Connection Failed", error)

    def _connection_ended(self):
        """Handle connection end"""
        self.update_status(False, "Disconnected")
        self.connect_btn.configure(state=tk.NORMAL)
        self.log_message("Disconnected from gateway", "info")

    def disconnect(self):
        """Disconnect from the gateway"""
        self.log_message("Disconnecting...", "info")
        self.update_status(False)

    def run(self):
        """Start the GUI application"""
        self.root.mainloop()


class GUILogHandler(logging.Handler):
    """Custom logging handler that writes to the GUI"""

    def __init__(self, gui: GatewayAgentGUI):
        super().__init__()
        self.gui = gui

    def emit(self, record):
        try:
            msg = self.format(record)
            level = "info"
            if record.levelno >= logging.ERROR:
                level = "error"
            elif record.levelno >= logging.WARNING:
                level = "warning"
            elif "success" in msg.lower() or "connected" in msg.lower():
                level = "success"

            self.gui.root.after(0, lambda: self.gui.log_message(msg, level))
        except:
            pass


def main_gui(token: str = None, saas_url: str = None, database: str = None, auto_connect: bool = False):
    """Entry point for GUI application with optional pre-filled values"""
    app = GatewayAgentGUI(token=token, saas_url=saas_url, database=database)

    # Auto-connect after GUI initializes if requested
    if auto_connect and token:
        def delayed_connect():
            # Wait for database discovery to complete (happens at 500ms + thread time)
            # Then connect automatically
            app.root.after(5000, app.connect)
        app.root.after(100, delayed_connect)

    app.run()


if __name__ == "__main__":
    # Parse command line for pre-filled values
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", help="Pre-fill gateway token")
    parser.add_argument("--url", help="Gateway WebSocket URL")
    parser.add_argument("--database", help="Pre-select database")
    parser.add_argument("--auto-connect", action="store_true", help="Automatically connect after GUI starts")
    args = parser.parse_args()

    main_gui(token=args.token, saas_url=args.url, database=args.database, auto_connect=args.auto_connect)
