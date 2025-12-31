"""
OryggiAI Gateway Agent - Windows Service

Runs the gateway agent as a Windows Service for:
- Automatic startup with Windows
- Background operation without user login
- System tray integration

Requires: pywin32 (pip install pywin32)
"""

import sys
import os
import asyncio
import logging
import json
from pathlib import Path

# Only import win32 modules on Windows
if sys.platform == "win32":
    try:
        import win32serviceutil
        import win32service
        import win32event
        import servicemanager
        import socket
        HAS_WIN32 = True
    except ImportError:
        HAS_WIN32 = False
else:
    HAS_WIN32 = False

try:
    from .config import load_config, AgentConfig, DatabaseConfig, GatewayConfig
    from .database import LocalDatabaseManager
    from .connection import GatewayConnection
except ImportError:
    try:
        # Frozen exe (PyInstaller)
        from gateway_agent.config import load_config, AgentConfig, DatabaseConfig, GatewayConfig
        from gateway_agent.database import LocalDatabaseManager
        from gateway_agent.connection import GatewayConnection
    except ImportError:
        # Standalone script
        from config import load_config, AgentConfig, DatabaseConfig, GatewayConfig
        from database import LocalDatabaseManager
        from connection import GatewayConnection


# Service configuration file location
SERVICE_CONFIG_PATH = os.path.join(
    os.environ.get("PROGRAMDATA", "C:\\ProgramData"),
    "OryggiAI",
    "gateway-config.json"
)


def get_service_config() -> dict:
    """Load service configuration from JSON file"""
    if os.path.exists(SERVICE_CONFIG_PATH):
        # Use utf-8-sig to handle BOM from PowerShell's Out-File
        with open(SERVICE_CONFIG_PATH, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    return {}


def save_service_config(config: dict):
    """Save service configuration to JSON file"""
    os.makedirs(os.path.dirname(SERVICE_CONFIG_PATH), exist_ok=True)
    with open(SERVICE_CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)


if HAS_WIN32:
    class OryggiGatewayService(win32serviceutil.ServiceFramework):
        """
        Windows Service wrapper for OryggiAI Gateway Agent

        This service:
        - Starts automatically with Windows
        - Runs in the background without user login
        - Auto-reconnects on connection loss
        - Uses Windows Authentication for database access
        """

        _svc_name_ = "OryggiGatewayAgent"
        _svc_display_name_ = "OryggiAI Gateway Agent"
        _svc_description_ = "Connects your local SQL Server database to OryggiAI cloud platform for natural language querying."

        def __init__(self, args):
            win32serviceutil.ServiceFramework.__init__(self, args)
            self.stop_event = win32event.CreateEvent(None, 0, 0, None)
            self.running = True
            self.logger = self._setup_logging()

        def _setup_logging(self):
            """Setup logging for service"""
            log_dir = os.path.join(
                os.environ.get("PROGRAMDATA", "C:\\ProgramData"),
                "OryggiAI",
                "logs"
            )
            os.makedirs(log_dir, exist_ok=True)

            logger = logging.getLogger("gateway_agent")
            logger.setLevel(logging.INFO)

            # File handler
            from logging.handlers import RotatingFileHandler
            handler = RotatingFileHandler(
                os.path.join(log_dir, "gateway-service.log"),
                maxBytes=10 * 1024 * 1024,
                backupCount=5
            )
            handler.setFormatter(logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(name)s - %(message)s"
            ))
            logger.addHandler(handler)

            return logger

        def SvcStop(self):
            """Stop the service"""
            self.logger.info("Service stop requested")
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            win32event.SetEvent(self.stop_event)
            self.running = False

        def SvcDoRun(self):
            """Main service entry point"""
            servicemanager.LogMsg(
                servicemanager.EVENTLOG_INFORMATION_TYPE,
                servicemanager.PYS_SERVICE_STARTED,
                (self._svc_name_, '')
            )
            self.logger.info("OryggiAI Gateway Service starting...")
            self.main()

        def main(self):
            """Main service loop - runs in a separate thread to handle asyncio properly"""
            import threading

            try:
                # Load configuration
                config_data = get_service_config()

                if not config_data:
                    self.logger.error("No configuration found at: " + SERVICE_CONFIG_PATH)
                    self.logger.error("Please run the installer or configure manually.")
                    servicemanager.LogErrorMsg("OryggiAI Gateway: No configuration found")
                    return

                self.logger.info(f"Configuration loaded from: {SERVICE_CONFIG_PATH}")

                # Build AgentConfig from saved data
                db_config = DatabaseConfig(
                    host=config_data.get("db_host", "localhost"),
                    port=int(config_data.get("db_port", 1433)),
                    database=config_data.get("db_database", ""),
                    username=config_data.get("db_username", ""),
                    password=config_data.get("db_password", ""),
                    use_windows_auth=config_data.get("use_windows_auth", True),
                    driver=config_data.get("db_driver", "ODBC Driver 17 for SQL Server"),
                )

                gateway_config = GatewayConfig(
                    gateway_token=config_data.get("gateway_token", ""),
                    saas_url=config_data.get("saas_url", "ws://103.197.77.163:3000/api/gateway/ws"),
                )

                if not gateway_config.gateway_token:
                    self.logger.error("Gateway token not configured!")
                    servicemanager.LogErrorMsg("OryggiAI Gateway: Gateway token not configured")
                    return

                if not db_config.database:
                    self.logger.error("Database not configured!")
                    servicemanager.LogErrorMsg("OryggiAI Gateway: Database not configured")
                    return

                # Create database manager
                database = LocalDatabaseManager(db_config)

                # Test database connection
                self.logger.info(f"Testing database connection to: {db_config.host}/{db_config.database}")
                db_test = database.test_connection()
                if not db_test["success"]:
                    self.logger.error(f"Database connection failed: {db_test.get('error')}")
                    servicemanager.LogErrorMsg(f"OryggiAI Gateway: Database connection failed - {db_test.get('error')}")
                    return

                self.logger.info(f"Connected to database: {db_config.database}")

                # Create gateway connection
                connection = GatewayConnection(gateway_config, database)
                self.connection = connection

                # Run async event loop in a dedicated thread
                def run_async_loop():
                    """Run the asyncio event loop in a separate thread"""
                    # Set event loop policy for Windows
                    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    self.loop = loop

                    async def connection_loop():
                        """Main connection loop with auto-reconnect"""
                        while self.running:
                            try:
                                self.logger.info("Connecting to OryggiAI gateway...")
                                await connection.run()
                            except asyncio.CancelledError:
                                self.logger.info("Connection cancelled")
                                break
                            except Exception as e:
                                self.logger.error(f"Connection error: {e}")
                                if self.running:
                                    self.logger.info("Reconnecting in 5 seconds...")
                                    await asyncio.sleep(5)

                    try:
                        loop.run_until_complete(connection_loop())
                    except Exception as e:
                        self.logger.error(f"Event loop error: {e}")
                    finally:
                        try:
                            loop.run_until_complete(connection.disconnect())
                        except:
                            pass
                        loop.close()

                # Start async loop in background thread
                self.async_thread = threading.Thread(target=run_async_loop, daemon=True)
                self.async_thread.start()
                self.logger.info("Gateway connection thread started")

                # Wait for stop signal from Windows Service Manager
                while self.running:
                    # Check for stop event every second
                    result = win32event.WaitForSingleObject(self.stop_event, 1000)
                    if result == win32event.WAIT_OBJECT_0:
                        self.logger.info("Stop event received")
                        break

                # Stop the async loop
                self.running = False
                if hasattr(self, 'loop') and self.loop:
                    self.loop.call_soon_threadsafe(self.loop.stop)

                # Wait for thread to finish
                if hasattr(self, 'async_thread') and self.async_thread.is_alive():
                    self.async_thread.join(timeout=5)

            except Exception as e:
                self.logger.error(f"Service error: {e}")
                import traceback
                self.logger.error(traceback.format_exc())
                servicemanager.LogErrorMsg(f"OryggiAI Gateway Service error: {e}")

            self.logger.info("OryggiAI Gateway Service stopped")


def install_service(config_data: dict) -> bool:
    """
    Install the Windows Service with the given configuration

    Args:
        config_data: Dictionary with configuration values

    Returns:
        True if installation successful
    """
    if not HAS_WIN32:
        print("Error: pywin32 is required for Windows Service installation")
        print("Install it with: pip install pywin32")
        return False

    try:
        # Save configuration
        save_service_config(config_data)
        print(f"Configuration saved to: {SERVICE_CONFIG_PATH}")

        # Install the service
        # Get the path to this module
        module_path = os.path.abspath(__file__)

        # Install using win32serviceutil
        win32serviceutil.InstallService(
            OryggiGatewayService._svc_name_,
            OryggiGatewayService._svc_display_name_,
            startType=win32service.SERVICE_AUTO_START,
            description=OryggiGatewayService._svc_description_,
        )

        print(f"Service '{OryggiGatewayService._svc_display_name_}' installed successfully!")
        print("Starting service...")

        # Start the service
        win32serviceutil.StartService(OryggiGatewayService._svc_name_)
        print("Service started!")

        return True

    except Exception as e:
        print(f"Error installing service: {e}")
        return False


def uninstall_service() -> bool:
    """
    Uninstall the Windows Service

    Returns:
        True if uninstallation successful
    """
    if not HAS_WIN32:
        print("Error: pywin32 is required")
        return False

    try:
        # Stop the service first
        try:
            win32serviceutil.StopService(OryggiGatewayService._svc_name_)
            print("Service stopped")
        except:
            pass

        # Remove the service
        win32serviceutil.RemoveService(OryggiGatewayService._svc_name_)
        print(f"Service '{OryggiGatewayService._svc_display_name_}' uninstalled successfully!")

        # Remove configuration
        if os.path.exists(SERVICE_CONFIG_PATH):
            os.remove(SERVICE_CONFIG_PATH)
            print("Configuration removed")

        return True

    except Exception as e:
        print(f"Error uninstalling service: {e}")
        return False


def check_service_status() -> str:
    """
    Check the status of the Windows Service

    Returns:
        Status string: 'running', 'stopped', 'not_installed'
    """
    if not HAS_WIN32:
        return "not_available"

    try:
        status = win32serviceutil.QueryServiceStatus(OryggiGatewayService._svc_name_)
        state = status[1]

        if state == win32service.SERVICE_RUNNING:
            return "running"
        elif state == win32service.SERVICE_STOPPED:
            return "stopped"
        elif state == win32service.SERVICE_START_PENDING:
            return "starting"
        elif state == win32service.SERVICE_STOP_PENDING:
            return "stopping"
        else:
            return "unknown"

    except Exception:
        return "not_installed"


def run_console_mode():
    """
    Run the gateway agent in console mode (not as a Windows Service).
    This is used by NSSM or for testing.
    """
    import signal

    # Setup logging
    log_dir = os.path.join(
        os.environ.get("PROGRAMDATA", "C:\\ProgramData"),
        "OryggiAI",
        "logs"
    )
    os.makedirs(log_dir, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(os.path.join(log_dir, "gateway-console.log"))
        ]
    )
    logger = logging.getLogger("gateway_agent")

    running = True

    def signal_handler(signum, frame):
        nonlocal running
        logger.info("Shutdown signal received")
        running = False

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Load configuration
        config_data = get_service_config()

        if not config_data:
            logger.error(f"No configuration found at: {SERVICE_CONFIG_PATH}")
            return 1

        logger.info(f"Configuration loaded from: {SERVICE_CONFIG_PATH}")

        # Build configs
        db_config = DatabaseConfig(
            host=config_data.get("db_host", "localhost"),
            port=int(config_data.get("db_port", 1433)),
            database=config_data.get("db_database", ""),
            username=config_data.get("db_username", ""),
            password=config_data.get("db_password", ""),
            use_windows_auth=config_data.get("use_windows_auth", True),
            driver=config_data.get("db_driver", "ODBC Driver 17 for SQL Server"),
        )

        gateway_config = GatewayConfig(
            gateway_token=config_data.get("gateway_token", ""),
            saas_url=config_data.get("saas_url", "ws://103.197.77.163:3000/api/gateway/ws"),
        )

        if not gateway_config.gateway_token:
            logger.error("Gateway token not configured!")
            return 1

        if not db_config.database:
            logger.error("Database not configured!")
            return 1

        # Create database manager
        database = LocalDatabaseManager(db_config)

        # Test database connection
        logger.info(f"Testing database connection to: {db_config.host}/{db_config.database}")
        db_test = database.test_connection()
        if not db_test["success"]:
            logger.error(f"Database connection failed: {db_test.get('error')}")
            return 1

        logger.info(f"Connected to database: {db_config.database}")

        # Create gateway connection
        connection = GatewayConnection(gateway_config, database)

        # Set event loop policy for Windows
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

        async def connection_loop():
            """Main connection loop with auto-reconnect"""
            while running:
                try:
                    logger.info("Connecting to OryggiAI gateway...")
                    await connection.run()
                except asyncio.CancelledError:
                    logger.info("Connection cancelled")
                    break
                except Exception as e:
                    logger.error(f"Connection error: {e}")
                    if running:
                        logger.info("Reconnecting in 5 seconds...")
                        await asyncio.sleep(5)

        # Run the event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            loop.run_until_complete(connection_loop())
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        finally:
            try:
                loop.run_until_complete(connection.disconnect())
            except:
                pass
            loop.close()

        logger.info("Gateway agent stopped")
        return 0

    except Exception as e:
        logger.error(f"Fatal error: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 1


if __name__ == "__main__":
    # Check for console mode (used by NSSM)
    if "--console" in sys.argv or "--run" in sys.argv or "-c" in sys.argv:
        sys.exit(run_console_mode())

    if HAS_WIN32:
        if len(sys.argv) == 1:
            # No args - assume called by NSSM, run in console mode
            sys.exit(run_console_mode())
        else:
            # Handle command line (install, remove, start, stop)
            win32serviceutil.HandleCommandLine(OryggiGatewayService)
    else:
        print("Windows Service support requires pywin32")
        print("Install with: pip install pywin32")
