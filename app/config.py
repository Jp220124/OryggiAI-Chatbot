"""
Configuration Management for Advance Chatbot
Uses Pydantic Settings for type-safe configuration
"""

from typing import List, Optional
from urllib.parse import quote_plus
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    """
    Application Settings loaded from environment variables
    """

    # ==================== Application ====================
    app_name: str = Field(default="Advance Chatbot", env="APP_NAME")
    app_version: str = Field(default="1.0.0", env="APP_VERSION")
    environment: str = Field(default="development", env="ENVIRONMENT")
    debug: bool = Field(default=True, env="DEBUG")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")

    # Server
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=9000, env="PORT")

    # ==================== Google Gemini ====================
    gemini_api_key: str = Field(default="", env="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-2.0-flash", env="GEMINI_MODEL")
    gemini_temperature: float = Field(default=0.0, env="GEMINI_TEMPERATURE")
    gemini_max_tokens: int = Field(default=2000, env="GEMINI_MAX_TOKENS")

    # ==================== OpenRouter (Backup LLM Provider) ====================
    openrouter_api_key: str = Field(default="", env="OPENROUTER_API_KEY")
    openrouter_model: str = Field(default="tngtech/deepseek-r1t2-chimera:free", env="OPENROUTER_MODEL")
    openrouter_base_url: str = Field(default="https://openrouter.ai/api/v1", env="OPENROUTER_BASE_URL")
    llm_provider: str = Field(default="gemini", env="LLM_PROVIDER")  # "gemini" (primary) or "openrouter" (backup)

    # ==================== Database ====================
    db_driver: str = Field(default="ODBC Driver 17 for SQL Server", env="DB_DRIVER")
    db_server: str = Field(..., env="DB_SERVER")
    db_instance: Optional[str] = Field(default=None, env="DB_INSTANCE")  # SQL Server named instance
    db_port: int = Field(default=1433, env="DB_PORT")
    db_name: str = Field(..., env="DB_NAME")

    @property
    def db_server_full(self) -> str:
        """Get full server name including instance if specified"""
        if self.db_instance:
            return f"{self.db_server}\\{self.db_instance}"
        return self.db_server
    db_use_windows_auth: bool = Field(default=False, env="DB_USE_WINDOWS_AUTH")
    db_username: Optional[str] = Field(default=None, env="DB_USERNAME")
    db_password: Optional[str] = Field(default=None, env="DB_PASSWORD")

    # Connection Pool
    db_pool_size: int = Field(default=10, env="DB_POOL_SIZE")
    db_pool_timeout: int = Field(default=30, env="DB_POOL_TIMEOUT")
    db_max_overflow: int = Field(default=20, env="DB_MAX_OVERFLOW")

    @property
    def database_url(self) -> str:
        """Build SQL Server connection string"""
        driver = self.db_driver.replace(' ', '+')

        if self.db_use_windows_auth:
            # Windows Authentication (Trusted Connection)
            return (
                f"mssql+pyodbc://{self.db_server_full}/{self.db_name}"
                f"?driver={driver}&Trusted_Connection=yes"
            )
        else:
            # SQL Server Authentication
            if not self.db_username or not self.db_password:
                raise ValueError("DB_USERNAME and DB_PASSWORD required when not using Windows Authentication")
            # URL-encode password to handle special characters like @ and !
            encoded_password = quote_plus(self.db_password)
            return (
                f"mssql+pyodbc://{self.db_username}:{encoded_password}"
                f"@{self.db_server_full}:{self.db_port}/{self.db_name}"
                f"?driver={driver}"
            )

    @property
    def pyodbc_connection_string(self) -> str:
        """Build raw pyodbc connection string for direct connections"""
        if self.db_use_windows_auth:
            return (
                f"DRIVER={{{self.db_driver}}};"
                f"SERVER={self.db_server_full};"
                f"DATABASE={self.db_name};"
                f"Trusted_Connection=yes;"
            )
        else:
            if not self.db_username or not self.db_password:
                raise ValueError("DB_USERNAME and DB_PASSWORD required")
            return (
                f"DRIVER={{{self.db_driver}}};"
                f"SERVER={self.db_server_full},{self.db_port};"
                f"DATABASE={self.db_name};"
                f"UID={self.db_username};"
                f"PWD={self.db_password};"
            )

    # ==================== FAISS (Vector Store) ====================
    faiss_index_path: str = Field(default="./data/faiss_index", env="FAISS_INDEX_PATH")

    # Embedding Model
    embedding_provider: str = Field(
        default="sentence-transformers",
        env="EMBEDDING_PROVIDER"
    )
    embedding_model: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        env="EMBEDDING_MODEL"
    )
    embedding_device: str = Field(default="cpu", env="EMBEDDING_DEVICE")

    # Google Embedding Configuration
    google_embedding_model: str = Field(
        default="models/text-embedding-004",
        env="GOOGLE_EMBEDDING_MODEL"
    )
    google_embedding_task_type: str = Field(
        default="retrieval_document",
        env="GOOGLE_EMBEDDING_TASK_TYPE"
    )

    # ==================== LangGraph ====================
    langgraph_max_iterations: int = Field(default=10, env="LANGGRAPH_MAX_ITERATIONS")
    langgraph_timeout: int = Field(default=60, env="LANGGRAPH_TIMEOUT")

    # ==================== Security & Authentication ====================
    secret_key: str = Field(..., env="SECRET_KEY")
    algorithm: str = Field(default="HS256", env="ALGORITHM")
    access_token_expire_minutes: int = Field(default=30, env="ACCESS_TOKEN_EXPIRE_MINUTES")

    # CORS
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8000"],
        env="CORS_ORIGINS"
    )

    # ==================== Email Configuration ====================
    sendgrid_api_key: Optional[str] = Field(default=None, env="SENDGRID_API_KEY")
    sendgrid_from_email: str = Field(default="noreply@yourcompany.com", env="SENDGRID_FROM_EMAIL")
    sendgrid_from_name: str = Field(default="Advance Chatbot", env="SENDGRID_FROM_NAME")

    # Alternative SMTP
    smtp_server: Optional[str] = Field(default=None, env="SMTP_SERVER")
    smtp_port: Optional[int] = Field(default=587, env="SMTP_PORT")
    smtp_username: Optional[str] = Field(default=None, env="SMTP_USERNAME")
    smtp_password: Optional[str] = Field(default=None, env="SMTP_PASSWORD")
    smtp_use_tls: bool = Field(default=True, env="SMTP_USE_TLS")

    # ==================== Report Generation ====================
    reports_output_dir: str = Field(default="./reports_output", env="REPORTS_OUTPUT_DIR")
    reports_max_rows: int = Field(default=10000, env="REPORTS_MAX_ROWS")
    reports_default_format: str = Field(default="pdf", env="REPORTS_DEFAULT_FORMAT")

    # PDF Configuration
    pdf_page_size: str = Field(default="A4", env="PDF_PAGE_SIZE")
    pdf_font_family: str = Field(default="Arial", env="PDF_FONT_FAMILY")

    # ==================== RBAC ====================
    default_admin_user: str = Field(default="admin", env="DEFAULT_ADMIN_USER")
    default_admin_password: str = Field(default="changeme123", env="DEFAULT_ADMIN_PASSWORD")

    roles: List[str] = Field(
        default=["ADMIN", "HR_MANAGER", "HR_STAFF", "VIEWER"],
        env="ROLES"
    )

    # ==================== Action Execution ====================
    require_action_confirmation: bool = Field(default=True, env="REQUIRE_ACTION_CONFIRMATION")
    action_timeout_seconds: int = Field(default=300, env="ACTION_TIMEOUT_SECONDS")

    # ==================== Oryggi Access Control API ====================
    # API endpoint for the Oryggi Access Control system
    access_control_api_url: str = Field(
        default="https://localhost/OryggiWebServceCoreApi/OryggiWebApi",
        env="ACCESS_CONTROL_API_URL"
    )
    access_control_api_key: str = Field(
        default="uw0RyC0v+aBV6nCWKM0M0Q==",
        env="ACCESS_CONTROL_API_KEY"
    )
    access_control_client_version: str = Field(
        default="24.07.2025",
        env="ACCESS_CONTROL_CLIENT_VERSION"
    )
    access_control_mock_mode: bool = Field(
        default=False,  # Set to False to use real Oryggi API
        env="ACCESS_CONTROL_MOCK_MODE"
    )
    # Default authentication type for access grants (5=Face, 2=Fingerprint)
    access_control_default_auth_type: int = Field(
        default=5,
        env="ACCESS_CONTROL_DEFAULT_AUTH_TYPE"
    )
    # Default schedule ID (63=All Access, 0=No Access)
    access_control_default_schedule: int = Field(
        default=63,
        env="ACCESS_CONTROL_DEFAULT_SCHEDULE"
    )

    # ==================== Extended Access Control (Phase 6) ====================
    # Database backup configuration
    database_backup_path: str = Field(
        default="D:\\Oryggi_Backups",
        env="DATABASE_BACKUP_PATH"
    )
    database_backup_retention_days: int = Field(
        default=30,
        env="DATABASE_BACKUP_RETENTION_DAYS"
    )

    # Visitor registration defaults
    visitor_default_category: int = Field(
        default=4,
        env="VISITOR_DEFAULT_CATEGORY"
    )
    visitor_default_duration_hours: int = Field(
        default=8,
        env="VISITOR_DEFAULT_DURATION_HOURS"
    )

    # Card enrollment defaults
    card_enrollment_default_auth_type: int = Field(
        default=1001,  # 1001=Card, 2=Fingerprint, 5=Face
        env="CARD_ENROLLMENT_DEFAULT_AUTH_TYPE"
    )
    card_enrollment_default_validity_days: int = Field(
        default=365,
        env="CARD_ENROLLMENT_DEFAULT_VALIDITY_DAYS"
    )

    # ==================== Platform Database (Multi-Tenant SaaS) ====================
    # This database stores tenant metadata, users, and platform configuration
    # Separate from tenant databases which store business data

    platform_db_server: str = Field(default="localhost", env="PLATFORM_DB_SERVER")
    platform_db_instance: Optional[str] = Field(default=None, env="PLATFORM_DB_INSTANCE")  # SQL Server named instance
    platform_db_port: int = Field(default=1433, env="PLATFORM_DB_PORT")
    platform_db_name: str = Field(default="OryggiAI_Platform", env="PLATFORM_DB_NAME")

    @property
    def platform_db_server_full(self) -> str:
        """Get full platform server name including instance if specified"""
        if self.platform_db_instance:
            return f"{self.platform_db_server}\\{self.platform_db_instance}"
        return self.platform_db_server
    platform_db_use_windows_auth: bool = Field(default=True, env="PLATFORM_DB_USE_WINDOWS_AUTH")
    platform_db_username: Optional[str] = Field(default=None, env="PLATFORM_DB_USERNAME")
    platform_db_password: Optional[str] = Field(default=None, env="PLATFORM_DB_PASSWORD")

    # Platform DB Connection Pool
    platform_db_pool_size: int = Field(default=5, env="PLATFORM_DB_POOL_SIZE")
    platform_db_pool_timeout: int = Field(default=30, env="PLATFORM_DB_POOL_TIMEOUT")
    platform_db_max_overflow: int = Field(default=10, env="PLATFORM_DB_MAX_OVERFLOW")

    @property
    def platform_database_url(self) -> str:
        """Build SQL Server connection string for Platform Database"""
        driver = self.db_driver.replace(' ', '+')

        if self.platform_db_use_windows_auth:
            # Windows Authentication (Trusted Connection)
            return (
                f"mssql+pyodbc://{self.platform_db_server_full}/{self.platform_db_name}"
                f"?driver={driver}&Trusted_Connection=yes"
            )
        else:
            # SQL Server Authentication
            if not self.platform_db_username or not self.platform_db_password:
                raise ValueError("PLATFORM_DB_USERNAME and PLATFORM_DB_PASSWORD required")
            # URL-encode password to handle special characters like @ and !
            encoded_password = quote_plus(self.platform_db_password)
            return (
                f"mssql+pyodbc://{self.platform_db_username}:{encoded_password}"
                f"@{self.platform_db_server_full}:{self.platform_db_port}/{self.platform_db_name}"
                f"?driver={driver}"
            )

    # ==================== JWT & Security (Multi-Tenant) ====================
    jwt_secret_key: str = Field(default="your-super-secret-jwt-key-change-in-production", env="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", env="JWT_ALGORITHM")
    jwt_access_token_expire_minutes: int = Field(default=30, env="JWT_ACCESS_TOKEN_EXPIRE_MINUTES")
    jwt_refresh_token_expire_days: int = Field(default=7, env="JWT_REFRESH_TOKEN_EXPIRE_DAYS")

    # Fernet key for encrypting database credentials (32 bytes, base64 encoded)
    encryption_key: str = Field(
        default="your-32-byte-fernet-key-base64==",
        env="ENCRYPTION_KEY"
    )

    # ==================== Gateway Agent ====================
    # WebSocket URL for gateway agents to connect to
    # In production, this should be set to the public URL of your server
    # Note: Using port 3000 directly as IIS/ARR has WebSocket proxy issues
    # e.g., ws://103.197.77.163:3000/api/gateway/ws or wss://yourdomain.com/api/gateway/ws
    gateway_ws_url: str = Field(
        default="ws://localhost:3000/api/gateway/ws",
        env="GATEWAY_WS_URL"
    )

    # ==================== Logging ====================
    log_dir: str = Field(default="./logs", env="LOG_DIR")
    log_file: str = Field(default="advance_chatbot.log", env="LOG_FILE")
    log_rotation: str = Field(default="10 MB", env="LOG_ROTATION")
    log_retention: str = Field(default="30 days", env="LOG_RETENTION")

    # Audit Logging
    enable_audit_log: bool = Field(default=True, env="ENABLE_AUDIT_LOG")
    audit_log_file: str = Field(default="audit.log", env="AUDIT_LOG_FILE")

    # ==================== Rate Limiting ====================
    rate_limit_enabled: bool = Field(default=True, env="RATE_LIMIT_ENABLED")
    rate_limit_per_minute: int = Field(default=60, env="RATE_LIMIT_PER_MINUTE")

    # ==================== Cache ====================
    enable_cache: bool = Field(default=True, env="ENABLE_CACHE")
    cache_ttl_seconds: int = Field(default=3600, env="CACHE_TTL_SECONDS")

    # ==================== PostgreSQL Configuration (Conversation Memory - Phase 3) ====================
    use_postgres_for_conversations: bool = Field(default=True, env="USE_POSTGRES_FOR_CONVERSATIONS")

    # PostgreSQL Connection
    postgres_host: str = Field(default="localhost", env="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, env="POSTGRES_PORT")
    postgres_db: str = Field(default="chatbot_conversations", env="POSTGRES_DB")
    postgres_user: str = Field(default="chatbot_user", env="POSTGRES_USER")
    postgres_password: str = Field(default="chatbot_password_2025", env="POSTGRES_PASSWORD")

    # PostgreSQL Connection Pool
    postgres_pool_size: int = Field(default=10, env="POSTGRES_POOL_SIZE")
    postgres_pool_timeout: int = Field(default=30, env="POSTGRES_POOL_TIMEOUT")
    postgres_max_overflow: int = Field(default=20, env="POSTGRES_MAX_OVERFLOW")

    @property
    def postgres_url(self) -> str:
        """Build PostgreSQL connection string for conversation storage"""
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def postgres_dsn(self) -> str:
        """Build psycopg2-compatible DSN for direct psycopg2.connect() usage"""
        return (
            f"host={self.postgres_host} port={self.postgres_port} "
            f"dbname={self.postgres_db} user={self.postgres_user} "
            f"password={self.postgres_password}"
        )

    # ==================== ChromaDB Configuration (Phase 3 - RAG Memory) ====================
    chromadb_mode: str = Field(default="http", env="CHROMADB_MODE")
    chromadb_host: str = Field(default="localhost", env="CHROMADB_HOST")
    chromadb_port: int = Field(default=8000, env="CHROMADB_PORT")
    chromadb_persist_directory: str = Field(default="./chroma_db", env="CHROMADB_PERSIST_DIRECTORY")
    chromadb_collection_name: str = Field(default="conversation_memory", env="CHROMADB_COLLECTION_NAME")

    # RAG Schema Configuration
    chroma_persist_dir: str = Field(default="./data/chroma_db", env="CHROMA_PERSIST_DIR")
    chroma_collection_name: str = Field(default="database_schema", env="CHROMA_COLLECTION_NAME")

    # ==================== Testing ====================
    testing: bool = Field(default=False, env="TESTING")
    test_database_name: str = Field(default="test_chatbot_db", env="TEST_DATABASE_NAME")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_ignore_empty=True,
        extra="ignore"
    )


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance

    Returns:
        Settings instance loaded from environment variables
    """
    return Settings()


# Global settings instance
settings = get_settings()
