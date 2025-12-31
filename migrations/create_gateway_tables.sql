-- Migration: Create gateway_sessions and gateway_query_logs tables
-- Date: 2025-01-29
-- Description: Creates the gateway tables for tracking sessions and query logs

-- Create gateway_sessions table
IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'gateway_sessions')
BEGIN
    CREATE TABLE gateway_sessions (
        id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
        session_id NVARCHAR(100) NOT NULL UNIQUE,
        tenant_id UNIQUEIDENTIFIER NOT NULL,
        database_id UNIQUEIDENTIFIER NOT NULL,
        api_key_id UNIQUEIDENTIFIER NULL,
        agent_version NVARCHAR(50) NULL,
        agent_hostname NVARCHAR(255) NULL,
        agent_os NVARCHAR(100) NULL,
        agent_ip NVARCHAR(50) NULL,
        connected_at DATETIME NOT NULL DEFAULT GETUTCDATE(),
        disconnected_at DATETIME NULL,
        last_heartbeat_at DATETIME NULL,
        status NVARCHAR(50) DEFAULT 'active',
        disconnect_reason NVARCHAR(500) NULL,
        queries_executed INT DEFAULT 0,
        total_query_time_ms INT DEFAULT 0,
        errors_count INT DEFAULT 0,
        bytes_transferred INT DEFAULT 0,
        created_at DATETIME NOT NULL DEFAULT GETUTCDATE(),
        updated_at DATETIME NOT NULL DEFAULT GETUTCDATE()
    );

    -- Add foreign keys
    ALTER TABLE gateway_sessions
    ADD CONSTRAINT FK_gateway_sessions_tenant_id
    FOREIGN KEY (tenant_id) REFERENCES tenants(id);

    ALTER TABLE gateway_sessions
    ADD CONSTRAINT FK_gateway_sessions_database_id
    FOREIGN KEY (database_id) REFERENCES tenant_databases(id);

    ALTER TABLE gateway_sessions
    ADD CONSTRAINT FK_gateway_sessions_api_key_id
    FOREIGN KEY (api_key_id) REFERENCES api_keys(id);

    -- Add indexes
    CREATE INDEX IX_gateway_sessions_tenant_id ON gateway_sessions(tenant_id);
    CREATE INDEX IX_gateway_sessions_database_id ON gateway_sessions(database_id);
    CREATE INDEX IX_gateway_sessions_status ON gateway_sessions(status);
    CREATE INDEX IX_gateway_sessions_session_id ON gateway_sessions(session_id);

    PRINT 'Created table: gateway_sessions';
END
ELSE
BEGIN
    PRINT 'Table already exists: gateway_sessions';
END
GO

-- Create gateway_query_logs table
IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'gateway_query_logs')
BEGIN
    CREATE TABLE gateway_query_logs (
        id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
        request_id NVARCHAR(100) NOT NULL UNIQUE,
        session_id UNIQUEIDENTIFIER NULL,  -- Nullable for direct API queries
        tenant_id UNIQUEIDENTIFIER NOT NULL,
        database_id UNIQUEIDENTIFIER NOT NULL,
        user_id UNIQUEIDENTIFIER NULL,
        conversation_id NVARCHAR(100) NULL,

        -- Question & Query Details
        natural_language_question NVARCHAR(MAX) NULL,
        sql_query NVARCHAR(MAX) NOT NULL,
        query_hash NVARCHAR(64) NULL,

        -- AI Generation Details
        llm_model NVARCHAR(100) NULL,
        tokens_used INT NULL,
        generation_time_ms INT NULL,

        -- Execution Results
        status NVARCHAR(50) DEFAULT 'success',
        row_count INT DEFAULT 0,
        execution_time_ms INT NULL,
        error_message NVARCHAR(MAX) NULL,
        error_code NVARCHAR(50) NULL,

        -- Timing
        requested_at DATETIME NOT NULL DEFAULT GETUTCDATE(),
        completed_at DATETIME NULL,

        -- Audit fields
        created_at DATETIME NOT NULL DEFAULT GETUTCDATE(),
        updated_at DATETIME NOT NULL DEFAULT GETUTCDATE()
    );

    -- Add foreign keys
    ALTER TABLE gateway_query_logs
    ADD CONSTRAINT FK_gateway_query_logs_session_id
    FOREIGN KEY (session_id) REFERENCES gateway_sessions(id) ON DELETE CASCADE;

    ALTER TABLE gateway_query_logs
    ADD CONSTRAINT FK_gateway_query_logs_tenant_id
    FOREIGN KEY (tenant_id) REFERENCES tenants(id);

    ALTER TABLE gateway_query_logs
    ADD CONSTRAINT FK_gateway_query_logs_database_id
    FOREIGN KEY (database_id) REFERENCES tenant_databases(id);

    ALTER TABLE gateway_query_logs
    ADD CONSTRAINT FK_gateway_query_logs_user_id
    FOREIGN KEY (user_id) REFERENCES tenant_users(id);

    -- Add indexes
    CREATE INDEX IX_gateway_query_logs_tenant_id ON gateway_query_logs(tenant_id);
    CREATE INDEX IX_gateway_query_logs_database_id ON gateway_query_logs(database_id);
    CREATE INDEX IX_gateway_query_logs_session_id ON gateway_query_logs(session_id);
    CREATE INDEX IX_gateway_query_logs_user_id ON gateway_query_logs(user_id);
    CREATE INDEX IX_gateway_query_logs_request_id ON gateway_query_logs(request_id);
    CREATE INDEX IX_gateway_query_logs_query_hash ON gateway_query_logs(query_hash);
    CREATE INDEX IX_gateway_query_logs_conversation_id ON gateway_query_logs(conversation_id);
    CREATE INDEX IX_gateway_query_logs_status ON gateway_query_logs(status);
    CREATE INDEX IX_gateway_query_logs_requested_at ON gateway_query_logs(requested_at DESC);

    PRINT 'Created table: gateway_query_logs';
END
ELSE
BEGIN
    PRINT 'Table already exists: gateway_query_logs';
END
GO

-- Verify the tables
SELECT TABLE_NAME
FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_NAME IN ('gateway_sessions', 'gateway_query_logs')
ORDER BY TABLE_NAME;
GO

PRINT '=== Migration completed successfully ===';
GO
