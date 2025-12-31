"""
Configuration Management for Gateway Agent

Loads configuration from YAML or JSON file and environment variables.
"""

import os
import yaml
import json
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path


@dataclass
class DatabaseConfig:
    """Local SQL Server connection settings"""
    host: str = "localhost"
    port: int = 1433
    database: str = ""
    username: str = ""
    password: str = ""
    driver: str = "ODBC Driver 17 for SQL Server"
    use_windows_auth: bool = False
    connection_timeout: int = 30
    query_timeout: int = 60


@dataclass
class GatewayConfig:
    """Gateway connection settings"""
    saas_url: str = "wss://api.oryggi.ai/api/gateway/ws"
    gateway_token: str = ""
    heartbeat_interval: int = 30
    reconnect_delay: int = 5
    max_reconnect_attempts: int = 0  # 0 = infinite
    ssl_verify: bool = True


@dataclass
class LoggingConfig:
    """Logging settings"""
    level: str = "INFO"
    file: str = "gateway_agent.log"
    max_size_mb: int = 10
    backup_count: int = 5


@dataclass
class AgentConfig:
    """Complete agent configuration"""
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    gateway: GatewayConfig = field(default_factory=GatewayConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)


def load_config(config_path: Optional[str] = None) -> AgentConfig:
    """
    Load configuration from YAML or JSON file and environment variables

    Priority:
    1. Environment variables (highest)
    2. Config file
    3. Defaults (lowest)

    Supports:
    - YAML files (config.yaml) with nested structure
    - JSON files (gateway-config.json) with flat structure from native installer

    Args:
        config_path: Path to config file (YAML or JSON)

    Returns:
        AgentConfig instance
    """
    config = AgentConfig()

    # Try to load from config file
    if config_path is None:
        config_path = os.environ.get("GATEWAY_CONFIG_PATH", "config.yaml")

    config_file = Path(config_path)
    if config_file.exists():
        # Use utf-8-sig to handle BOM from PowerShell's Out-File
        with open(config_path, "r", encoding="utf-8-sig") as f:
            content = f.read()

        # Detect file type and parse accordingly
        file_config = {}
        if config_path.endswith(".json"):
            file_config = json.loads(content) or {}
        else:
            # Try YAML first, fall back to JSON if it looks like JSON
            try:
                file_config = yaml.safe_load(content) or {}
            except yaml.YAMLError:
                try:
                    file_config = json.loads(content) or {}
                except json.JSONDecodeError:
                    pass

        # Check if it's a flat JSON config from native installer
        # Native installer saves: gateway_token, saas_url, db_database, db_host, etc.
        if "gateway_token" in file_config and "database" not in file_config:
            # Flat JSON from native installer - map to nested structure
            if file_config.get("gateway_token"):
                config.gateway.gateway_token = file_config["gateway_token"]
            if file_config.get("saas_url"):
                config.gateway.saas_url = file_config["saas_url"]
            if file_config.get("db_database"):
                config.database.database = file_config["db_database"]
            if file_config.get("db_host"):
                config.database.host = file_config["db_host"]
            if file_config.get("db_port"):
                config.database.port = int(file_config["db_port"])
            if file_config.get("db_username"):
                config.database.username = file_config["db_username"]
            if file_config.get("db_password"):
                config.database.password = file_config["db_password"]
            if file_config.get("db_driver"):
                config.database.driver = file_config["db_driver"]
            if "use_windows_auth" in file_config:
                config.database.use_windows_auth = bool(file_config["use_windows_auth"])
        else:
            # Nested YAML/JSON config - apply normally
            if "database" in file_config:
                for key, value in file_config["database"].items():
                    if hasattr(config.database, key):
                        setattr(config.database, key, value)

            if "gateway" in file_config:
                for key, value in file_config["gateway"].items():
                    if hasattr(config.gateway, key):
                        setattr(config.gateway, key, value)

            if "logging" in file_config:
                for key, value in file_config["logging"].items():
                    if hasattr(config.logging, key):
                        setattr(config.logging, key, value)

    # Apply environment variables (override config file)
    env_mappings = {
        # Database
        "DB_HOST": ("database", "host"),
        "DB_PORT": ("database", "port", int),
        "DB_DATABASE": ("database", "database"),
        "DB_USERNAME": ("database", "username"),
        "DB_PASSWORD": ("database", "password"),
        "DB_DRIVER": ("database", "driver"),
        "DB_USE_WINDOWS_AUTH": ("database", "use_windows_auth", lambda x: x.lower() == "true"),
        "DB_CONNECTION_TIMEOUT": ("database", "connection_timeout", int),
        "DB_QUERY_TIMEOUT": ("database", "query_timeout", int),
        # Gateway
        "GATEWAY_SAAS_URL": ("gateway", "saas_url"),
        "GATEWAY_TOKEN": ("gateway", "gateway_token"),
        "GATEWAY_HEARTBEAT_INTERVAL": ("gateway", "heartbeat_interval", int),
        "GATEWAY_RECONNECT_DELAY": ("gateway", "reconnect_delay", int),
        "GATEWAY_MAX_RECONNECT_ATTEMPTS": ("gateway", "max_reconnect_attempts", int),
        "GATEWAY_SSL_VERIFY": ("gateway", "ssl_verify", lambda x: x.lower() == "true"),
        # Logging
        "LOG_LEVEL": ("logging", "level"),
        "LOG_FILE": ("logging", "file"),
    }

    for env_var, mapping in env_mappings.items():
        value = os.environ.get(env_var)
        if value is not None:
            section = mapping[0]
            key = mapping[1]
            converter = mapping[2] if len(mapping) > 2 else str

            section_obj = getattr(config, section)
            setattr(section_obj, key, converter(value))

    return config


def save_config_template(path: str = "config.yaml.example"):
    """Generate example config file"""
    template = """# OryggiAI Gateway Agent Configuration

# Local SQL Server Connection
database:
  host: "localhost"
  port: 1433
  database: "YourDatabaseName"
  username: "sa"
  password: "YourPassword"
  driver: "ODBC Driver 17 for SQL Server"
  use_windows_auth: false
  connection_timeout: 30
  query_timeout: 60

# Gateway Connection to OryggiAI SaaS
gateway:
  saas_url: "wss://api.oryggi.ai/api/gateway/ws"
  gateway_token: "gw_YOUR_TOKEN_HERE"
  heartbeat_interval: 30
  reconnect_delay: 5
  max_reconnect_attempts: 0  # 0 = infinite retries
  ssl_verify: true

# Logging Configuration
logging:
  level: "INFO"
  file: "gateway_agent.log"
  max_size_mb: 10
  backup_count: 5
"""
    with open(path, "w") as f:
        f.write(template)
    print(f"Config template saved to {path}")
