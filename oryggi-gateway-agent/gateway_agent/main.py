"""
OryggiAI Gateway Agent - Main Entry Point

Command-line interface for running the gateway agent.
"""

import asyncio
import argparse
import signal
import sys
import os
import logging
from pathlib import Path

# Native installer config location
NATIVE_CONFIG_PATH = os.path.join(
    os.environ.get("PROGRAMDATA", "C:\\ProgramData"),
    "OryggiAI",
    "gateway-config.json"
)

try:
    from .config import load_config, save_config_template, AgentConfig
    from .database import LocalDatabaseManager
    from .connection import GatewayConnection
except ImportError:
    try:
        # Frozen exe (PyInstaller)
        from gateway_agent.config import load_config, save_config_template, AgentConfig
        from gateway_agent.database import LocalDatabaseManager
        from gateway_agent.connection import GatewayConnection
    except ImportError:
        # Standalone script
        from config import load_config, save_config_template, AgentConfig
        from database import LocalDatabaseManager
        from connection import GatewayConnection


def setup_logging(config: AgentConfig):
    """Configure logging based on config"""
    from logging.handlers import RotatingFileHandler

    # Create logger
    logger = logging.getLogger("gateway_agent")
    logger.setLevel(getattr(logging, config.logging.level.upper()))

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(getattr(logging, config.logging.level.upper()))
    console_format = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console.setFormatter(console_format)
    logger.addHandler(console)

    # File handler
    if config.logging.file:
        file_handler = RotatingFileHandler(
            config.logging.file,
            maxBytes=config.logging.max_size_mb * 1024 * 1024,
            backupCount=config.logging.backup_count,
        )
        file_handler.setLevel(getattr(logging, config.logging.level.upper()))
        file_format = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(file_format)
        logger.addHandler(file_handler)

    return logger


class GatewayAgent:
    """
    Main Gateway Agent Application

    Coordinates database connection, gateway connection, and lifecycle.
    """

    def __init__(self, config: AgentConfig):
        self.config = config
        self.logger = logging.getLogger("gateway_agent.main")
        self.database = LocalDatabaseManager(config.database)
        self.connection = GatewayConnection(config.gateway, self.database)
        self._shutdown_event = asyncio.Event()

    async def start(self):
        """Start the gateway agent"""
        self.logger.info("=" * 60)
        self.logger.info("OryggiAI Gateway Agent Starting")
        self.logger.info("=" * 60)

        # Test database connection
        self.logger.info("Testing database connection...")
        db_test = self.database.test_connection()

        if not db_test["success"]:
            self.logger.error(f"Database connection failed: {db_test.get('error')}")
            self.logger.error("Please check your database configuration.")
            return False

        self.logger.info(f"Database: {db_test['database']}")
        self.logger.info(f"Version: {db_test['version']}")
        self.logger.info("Database connection successful")

        # Start gateway connection
        self.logger.info(f"Connecting to gateway: {self.config.gateway.saas_url}")

        try:
            await self.connection.run()
        except asyncio.CancelledError:
            self.logger.info("Gateway agent cancelled")
        except Exception as e:
            self.logger.error(f"Gateway connection error: {e}")
            return False

        return True

    async def stop(self):
        """Stop the gateway agent gracefully"""
        self.logger.info("Stopping gateway agent...")
        await self.connection.disconnect()
        self.database.disconnect()
        self.logger.info("Gateway agent stopped")

    def handle_signal(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Received signal {signum}, shutting down...")
        asyncio.create_task(self.stop())


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="OryggiAI Gateway Agent - Connect your local database to OryggiAI SaaS",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  gateway-agent                     Run with default config.yaml
  gateway-agent -c my-config.yaml   Run with custom config file
  gateway-agent --init              Create example config file
  gateway-agent --test              Test database connection only

Environment Variables:
  GATEWAY_TOKEN          Override gateway token from config
  DB_HOST                Override database host
  DB_DATABASE            Override database name
  DB_USERNAME            Override database username
  DB_PASSWORD            Override database password
        """,
    )

    # Determine default config path - check native installer location first
    default_config = "config.yaml"
    if os.path.exists(NATIVE_CONFIG_PATH):
        default_config = NATIVE_CONFIG_PATH

    parser.add_argument(
        "-c",
        "--config",
        default=default_config,
        help=f"Path to configuration file (default: {default_config})",
    )
    parser.add_argument(
        "--init",
        action="store_true",
        help="Create example configuration file",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Test database connection and exit",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Show version and exit",
    )

    args = parser.parse_args()

    # Show version
    if args.version:
        from . import __version__
        print(f"OryggiAI Gateway Agent v{__version__}")
        return 0

    # Create example config
    if args.init:
        output_path = "config.yaml.example"
        if Path("config.yaml").exists():
            output_path = "config.yaml.example"
        else:
            output_path = "config.yaml"
        save_config_template(output_path)
        return 0

    # Load configuration
    try:
        config = load_config(args.config)
    except Exception as e:
        print(f"Error loading config: {e}")
        print("Run 'gateway-agent --init' to create an example config file.")
        return 1

    # Override log level for verbose mode
    if args.verbose:
        config.logging.level = "DEBUG"

    # Setup logging
    logger = setup_logging(config)

    # Validate required config
    if not config.gateway.gateway_token:
        logger.error("Gateway token not configured!")
        logger.error("Set GATEWAY_TOKEN environment variable or add to config.yaml")
        return 1

    if not config.database.database:
        logger.error("Database name not configured!")
        logger.error("Set DB_DATABASE environment variable or add to config.yaml")
        return 1

    # Test mode - just test database connection
    if args.test:
        logger.info("Testing database connection...")
        database = LocalDatabaseManager(config.database)
        result = database.test_connection()

        if result["success"]:
            logger.info("Database connection successful!")
            logger.info(f"  Database: {result['database']}")
            logger.info(f"  Version: {result['version']}")
            return 0
        else:
            logger.error(f"Database connection failed: {result.get('error')}")
            return 1

    # Create and run agent
    agent = GatewayAgent(config)

    # Setup signal handlers
    if sys.platform != "win32":
        signal.signal(signal.SIGTERM, agent.handle_signal)
        signal.signal(signal.SIGINT, agent.handle_signal)

    # Run agent
    try:
        if sys.platform == "win32":
            # Windows requires different event loop handling
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

        success = asyncio.run(agent.start())
        return 0 if success else 1

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        asyncio.run(agent.stop())
        return 0
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
