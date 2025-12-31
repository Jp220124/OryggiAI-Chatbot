"""
OryggiAI Gateway Agent - GUI Application

A simple, user-friendly graphical interface for the Gateway Agent.
No Python knowledge required - just fill in the fields and click Connect!
"""

import asyncio
import threading
import logging
import sys
import os
from typing import Optional
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

# Import agent components - support both package and standalone/frozen modes
try:
    from .config import AgentConfig, DatabaseConfig, GatewayConfig, LoggingConfig
    from .database import LocalDatabaseManager
    from .connection import GatewayConnection
except ImportError:
    try:
        # Frozen exe (PyInstaller)
        from gateway_agent.config import AgentConfig, DatabaseConfig, GatewayConfig, LoggingConfig
        from gateway_agent.database import LocalDatabaseManager
        from gateway_agent.connection import GatewayConnection
    except ImportError:
        # Standalone script
        from config import AgentConfig, DatabaseConfig, GatewayConfig, LoggingConfig
        from database import LocalDatabaseManager
        from connection import GatewayConnection


class GatewayAgentGUI:
    """
    Graphical User Interface for OryggiAI Gateway Agent

    Provides a simple, intuitive interface for:
    - Entering gateway token
    - Configuring database connection
    - Testing database connection
    - Connecting to OryggiAI SaaS
    """

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("OryggiAI Gateway Agent")
        self.root.geometry("500x600")
        self.root.resizable(False, False)

        # Set icon if available
        try:
            icon_path = os.path.join(os.path.dirname(__file__), "icon.ico")
            if os.path.exists(icon_path):
                self.root.iconbitmap(icon_path)
        except:
            pass

        # Configure colors
        self.bg_color = "#1a1a2e"
        self.card_color = "#16213e"
        self.accent_color = "#667eea"
        self.text_color = "#ffffff"
        self.secondary_text = "#a0aec0"
        self.success_color = "#48bb78"
        self.error_color = "#fc8181"

        self.root.configure(bg=self.bg_color)

        # Variables
        self.gateway_token = tk.StringVar()
        self.saas_url = tk.StringVar(value="wss://api.oryggi.ai/api/gateway/ws")
        self.db_host = tk.StringVar(value="localhost")
        self.db_port = tk.StringVar(value="1433")
        self.db_database = tk.StringVar()
        self.db_username = tk.StringVar()
        self.db_password = tk.StringVar()
        self.use_windows_auth = tk.BooleanVar(value=False)

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
        # Main container
        main_frame = tk.Frame(self.root, bg=self.bg_color)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Header
        header_frame = tk.Frame(main_frame, bg=self.bg_color)
        header_frame.pack(fill=tk.X, pady=(0, 20))

        title_label = tk.Label(
            header_frame,
            text="OryggiAI Gateway Agent",
            font=("Segoe UI", 18, "bold"),
            fg=self.text_color,
            bg=self.bg_color
        )
        title_label.pack()

        subtitle_label = tk.Label(
            header_frame,
            text="Connect your local database to OryggiAI",
            font=("Segoe UI", 10),
            fg=self.secondary_text,
            bg=self.bg_color
        )
        subtitle_label.pack()

        # Gateway Token Section
        token_frame = self.create_section(main_frame, "Gateway Token")
        self.create_entry(token_frame, "Paste your token from dashboard:", self.gateway_token, show="*")

        # Database Section
        db_frame = self.create_section(main_frame, "SQL Server Connection")

        # Host and Port row
        row_frame = tk.Frame(db_frame, bg=self.card_color)
        row_frame.pack(fill=tk.X, pady=2)

        host_frame = tk.Frame(row_frame, bg=self.card_color)
        host_frame.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 5))
        self.create_entry(host_frame, "Server/Host:", self.db_host)

        port_frame = tk.Frame(row_frame, bg=self.card_color)
        port_frame.pack(side=tk.RIGHT, padx=(5, 0))
        self.create_entry(port_frame, "Port:", self.db_port, width=8)

        # Database name
        self.create_entry(db_frame, "Database Name:", self.db_database)

        # Username and Password row
        row_frame2 = tk.Frame(db_frame, bg=self.card_color)
        row_frame2.pack(fill=tk.X, pady=2)

        user_frame = tk.Frame(row_frame2, bg=self.card_color)
        user_frame.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 5))
        self.create_entry(user_frame, "Username:", self.db_username)

        pass_frame = tk.Frame(row_frame2, bg=self.card_color)
        pass_frame.pack(side=tk.RIGHT, expand=True, fill=tk.X, padx=(5, 0))
        self.create_entry(pass_frame, "Password:", self.db_password, show="*")

        # Windows Auth checkbox
        auth_frame = tk.Frame(db_frame, bg=self.card_color)
        auth_frame.pack(fill=tk.X, pady=5)

        self.auth_check = tk.Checkbutton(
            auth_frame,
            text="Use Windows Authentication",
            variable=self.use_windows_auth,
            font=("Segoe UI", 9),
            fg=self.secondary_text,
            bg=self.card_color,
            selectcolor=self.bg_color,
            activebackground=self.card_color,
            activeforeground=self.text_color,
            command=self.toggle_windows_auth
        )
        self.auth_check.pack(anchor=tk.W)

        # Buttons Section
        button_frame = tk.Frame(main_frame, bg=self.bg_color)
        button_frame.pack(fill=tk.X, pady=15)

        # Test Connection Button
        self.test_btn = tk.Button(
            button_frame,
            text="Test Connection",
            font=("Segoe UI", 10, "bold"),
            fg=self.text_color,
            bg="#4a5568",
            activebackground="#2d3748",
            activeforeground=self.text_color,
            relief=tk.FLAT,
            cursor="hand2",
            command=self.test_connection,
            width=15
        )
        self.test_btn.pack(side=tk.LEFT, padx=(0, 10))

        # Connect Button
        self.connect_btn = tk.Button(
            button_frame,
            text="Connect",
            font=("Segoe UI", 10, "bold"),
            fg=self.text_color,
            bg=self.accent_color,
            activebackground="#5a67d8",
            activeforeground=self.text_color,
            relief=tk.FLAT,
            cursor="hand2",
            command=self.toggle_connection,
            width=15
        )
        self.connect_btn.pack(side=tk.RIGHT)

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
            font=("Segoe UI", 9),
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
            height=8,
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
        self.log_text.tag_config("warning", foreground="#ecc94b")

    def create_section(self, parent, title):
        """Create a styled section frame"""
        section_label = tk.Label(
            parent,
            text=title,
            font=("Segoe UI", 10, "bold"),
            fg=self.secondary_text,
            bg=self.bg_color,
            anchor=tk.W
        )
        section_label.pack(fill=tk.X, pady=(10, 5))

        frame = tk.Frame(parent, bg=self.card_color)
        frame.pack(fill=tk.X, pady=(0, 10), ipady=10, ipadx=10)

        return frame

    def create_entry(self, parent, label_text, variable, show="", width=None):
        """Create a styled label and entry pair"""
        label = tk.Label(
            parent,
            text=label_text,
            font=("Segoe UI", 9),
            fg=self.secondary_text,
            bg=self.card_color,
            anchor=tk.W
        )
        label.pack(fill=tk.X, padx=5, pady=(5, 2))

        entry_kwargs = {
            "textvariable": variable,
            "font": ("Segoe UI", 10),
            "bg": "#0f0f23",
            "fg": self.text_color,
            "insertbackground": self.text_color,
            "relief": tk.FLAT,
            "highlightthickness": 1,
            "highlightbackground": "#2d3748",
            "highlightcolor": self.accent_color,
        }

        if width:
            entry_kwargs["width"] = width

        if show:
            entry_kwargs["show"] = show

        entry = tk.Entry(parent, **entry_kwargs)
        entry.pack(fill=tk.X, padx=5, pady=(0, 5))

        return entry

    def toggle_windows_auth(self):
        """Toggle username/password fields based on Windows Auth selection"""
        # In a full implementation, you would enable/disable username/password fields
        pass

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
            self.status_label.configure(text="Connected", fg=self.success_color)
            self.connect_btn.configure(text="Disconnect", bg=self.error_color)
        else:
            self.status_dot.itemconfig(1, fill="#6b7280")
            status_text = message if message else "Not connected"
            self.status_label.configure(text=status_text, fg=self.secondary_text)
            self.connect_btn.configure(text="Connect", bg=self.accent_color)

    def validate_inputs(self) -> bool:
        """Validate all input fields"""
        if not self.gateway_token.get().strip():
            messagebox.showerror("Error", "Gateway token is required!")
            return False

        if not self.gateway_token.get().startswith("gw_"):
            messagebox.showerror("Error", "Invalid gateway token format. Token should start with 'gw_'")
            return False

        if not self.db_host.get().strip():
            messagebox.showerror("Error", "Database host is required!")
            return False

        if not self.db_database.get().strip():
            messagebox.showerror("Error", "Database name is required!")
            return False

        if not self.use_windows_auth.get():
            if not self.db_username.get().strip():
                messagebox.showerror("Error", "Database username is required!")
                return False

        return True

    def get_config(self) -> AgentConfig:
        """Build configuration from GUI inputs"""
        db_config = DatabaseConfig(
            host=self.db_host.get().strip(),
            port=int(self.db_port.get().strip() or "1433"),
            database=self.db_database.get().strip(),
            username=self.db_username.get().strip(),
            password=self.db_password.get().strip(),
            use_windows_auth=self.use_windows_auth.get(),
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

    def test_connection(self):
        """Test the database connection"""
        if not self.validate_inputs():
            return

        self.log_message("Testing database connection...", "info")
        self.test_btn.configure(state=tk.DISABLED, text="Testing...")

        def do_test():
            try:
                config = self.get_config()
                database = LocalDatabaseManager(config.database)
                result = database.test_connection()

                self.root.after(0, lambda: self._test_complete(result))
            except Exception as e:
                self.root.after(0, lambda: self._test_complete({
                    "success": False,
                    "error": str(e)
                }))

        thread = threading.Thread(target=do_test, daemon=True)
        thread.start()

    def _test_complete(self, result):
        """Handle test connection completion"""
        self.test_btn.configure(state=tk.NORMAL, text="Test Connection")

        if result["success"]:
            self.log_message(f"Database connection successful!", "success")
            self.log_message(f"  Database: {result.get('database', 'N/A')}", "info")
            self.log_message(f"  Version: {result.get('version', 'N/A')}", "info")
            messagebox.showinfo("Success", "Database connection successful!")
        else:
            error_msg = result.get("error", "Unknown error")
            self.log_message(f"Connection failed: {error_msg}", "error")
            messagebox.showerror("Connection Failed", f"Could not connect to database:\n\n{error_msg}")

    def toggle_connection(self):
        """Connect or disconnect from the gateway"""
        if self.connected:
            self.disconnect()
        else:
            self.connect()

    def connect(self):
        """Start the gateway connection"""
        if not self.validate_inputs():
            return

        self.log_message("Starting gateway connection...", "info")
        self.connect_btn.configure(state=tk.DISABLED, text="Connecting...")

        def run_agent():
            try:
                config = self.get_config()

                # Test database first
                database = LocalDatabaseManager(config.database)
                db_result = database.test_connection()

                if not db_result["success"]:
                    self.root.after(0, lambda: self._connection_failed(
                        f"Database connection failed: {db_result.get('error')}"
                    ))
                    return

                self.root.after(0, lambda: self.log_message(
                    "Database connection verified", "success"
                ))

                # Create connection
                connection = GatewayConnection(config.gateway, database)

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
        self.log_message("Connected to OryggiAI gateway!", "success")

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
        # The agent thread will end naturally

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


def main_gui():
    """Entry point for GUI application"""
    app = GatewayAgentGUI()
    app.run()


if __name__ == "__main__":
    main_gui()
