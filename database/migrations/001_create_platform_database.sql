/*
================================================================================
OryggiAI Platform Database Schema
Version: 1.0.0
Created: 2025-11-26
Description: Multi-tenant SaaS platform database schema for OryggiAI Chatbot
================================================================================

This script creates the OryggiAI_Platform database with all tables needed
for multi-tenant SaaS architecture.

Usage:
    1. Run this script on your SQL Server instance
    2. Update the connection string in .env file
    3. Run the application

Tables:
    - tenants: Organization/company information
    - tenant_users: Users belonging to each tenant
    - tenant_databases: Database connections for each tenant
    - schema_cache: Auto-discovered schema metadata
    - few_shot_examples: Auto-generated Q&A pairs
    - usage_metrics: Daily usage tracking
    - audit_logs: Security and compliance audit trail
    - api_keys: API key management for programmatic access

================================================================================
*/

-- ============================================================================
-- CREATE DATABASE
-- ============================================================================

USE master;
GO

-- Check if database exists and create if not
IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = N'OryggiAI_Platform')
BEGIN
    CREATE DATABASE OryggiAI_Platform;
    PRINT 'Database OryggiAI_Platform created successfully.';
END
ELSE
BEGIN
    PRINT 'Database OryggiAI_Platform already exists.';
END
GO

USE OryggiAI_Platform;
GO

-- ============================================================================
-- TABLE: tenants
-- Description: Stores tenant/organization information
-- ============================================================================

IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'dbo.tenants') AND type = 'U')
BEGIN
    CREATE TABLE dbo.tenants (
        -- Primary Key
        id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),

        -- Tenant Identity
        name NVARCHAR(255) NOT NULL,
        slug NVARCHAR(100) NOT NULL UNIQUE,  -- URL-friendly identifier

        -- Organization Details
        organization_type NVARCHAR(100) NULL,  -- Auto-detected: university, hospital, retail
        industry NVARCHAR(100) NULL,
        company_size NVARCHAR(50) NULL,  -- small, medium, large, enterprise

        -- Contact Information
        admin_email NVARCHAR(255) NOT NULL,
        phone NVARCHAR(50) NULL,
        address NVARCHAR(500) NULL,
        country NVARCHAR(100) NULL,
        timezone NVARCHAR(50) DEFAULT 'Asia/Kolkata',

        -- Subscription & Status
        status NVARCHAR(50) DEFAULT 'pending',  -- pending, active, suspended, cancelled
        plan NVARCHAR(50) DEFAULT 'free',  -- free, starter, professional, enterprise
        trial_ends_at DATETIME2 NULL,

        -- Feature Flags (JSON)
        features NVARCHAR(MAX) NULL,  -- JSON: {"sql_agent": true, "reports": true, ...}

        -- Limits based on plan
        max_users INT DEFAULT 5,
        max_databases INT DEFAULT 1,
        max_queries_per_day INT DEFAULT 100,
        max_storage_mb INT DEFAULT 500,

        -- Branding
        logo_url NVARCHAR(500) NULL,
        primary_color NVARCHAR(20) NULL,

        -- Metadata
        created_at DATETIME2 DEFAULT GETUTCDATE(),
        updated_at DATETIME2 DEFAULT GETUTCDATE(),
        deleted_at DATETIME2 NULL,  -- Soft delete

        -- Constraints
        CONSTRAINT CHK_tenants_status CHECK (status IN ('pending', 'active', 'suspended', 'cancelled')),
        CONSTRAINT CHK_tenants_plan CHECK (plan IN ('free', 'starter', 'professional', 'enterprise'))
    );

    -- Create indexes
    CREATE INDEX IX_tenants_slug ON dbo.tenants(slug);
    CREATE INDEX IX_tenants_status ON dbo.tenants(status);
    CREATE INDEX IX_tenants_admin_email ON dbo.tenants(admin_email);
    CREATE INDEX IX_tenants_created_at ON dbo.tenants(created_at);

    PRINT 'Table dbo.tenants created successfully.';
END
GO

-- ============================================================================
-- TABLE: tenant_users
-- Description: Users belonging to each tenant
-- ============================================================================

IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'dbo.tenant_users') AND type = 'U')
BEGIN
    CREATE TABLE dbo.tenant_users (
        -- Primary Key
        id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),

        -- Tenant Relationship
        tenant_id UNIQUEIDENTIFIER NOT NULL,

        -- User Identity
        email NVARCHAR(255) NOT NULL,
        password_hash NVARCHAR(255) NOT NULL,

        -- Profile
        first_name NVARCHAR(100) NULL,
        last_name NVARCHAR(100) NULL,
        display_name NVARCHAR(200) NULL,
        avatar_url NVARCHAR(500) NULL,
        phone NVARCHAR(50) NULL,

        -- Role & Permissions
        role NVARCHAR(50) DEFAULT 'user',  -- owner, admin, manager, user, viewer
        permissions NVARCHAR(MAX) NULL,  -- JSON: ["read", "write", "delete", ...]

        -- Status
        is_active BIT DEFAULT 1,
        is_verified BIT DEFAULT 0,
        email_verified_at DATETIME2 NULL,

        -- Authentication
        last_login_at DATETIME2 NULL,
        last_login_ip NVARCHAR(50) NULL,
        failed_login_attempts INT DEFAULT 0,
        locked_until DATETIME2 NULL,

        -- Password Reset
        password_reset_token NVARCHAR(255) NULL,
        password_reset_expires DATETIME2 NULL,

        -- Two-Factor Authentication
        two_factor_enabled BIT DEFAULT 0,
        two_factor_secret NVARCHAR(255) NULL,

        -- Metadata
        preferences NVARCHAR(MAX) NULL,  -- JSON: UI preferences
        created_at DATETIME2 DEFAULT GETUTCDATE(),
        updated_at DATETIME2 DEFAULT GETUTCDATE(),
        deleted_at DATETIME2 NULL,

        -- Constraints
        CONSTRAINT FK_tenant_users_tenant FOREIGN KEY (tenant_id)
            REFERENCES dbo.tenants(id) ON DELETE CASCADE,
        CONSTRAINT UQ_tenant_users_email UNIQUE (tenant_id, email),
        CONSTRAINT CHK_tenant_users_role CHECK (role IN ('owner', 'admin', 'manager', 'user', 'viewer'))
    );

    -- Create indexes
    CREATE INDEX IX_tenant_users_tenant_id ON dbo.tenant_users(tenant_id);
    CREATE INDEX IX_tenant_users_email ON dbo.tenant_users(email);
    CREATE INDEX IX_tenant_users_role ON dbo.tenant_users(role);
    CREATE INDEX IX_tenant_users_is_active ON dbo.tenant_users(is_active);

    PRINT 'Table dbo.tenant_users created successfully.';
END
GO

-- ============================================================================
-- TABLE: tenant_databases
-- Description: Database connections for each tenant
-- ============================================================================

IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'dbo.tenant_databases') AND type = 'U')
BEGIN
    CREATE TABLE dbo.tenant_databases (
        -- Primary Key
        id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),

        -- Tenant Relationship
        tenant_id UNIQUEIDENTIFIER NOT NULL,

        -- Database Identity
        name NVARCHAR(255) NOT NULL,  -- e.g., "Main DB", "HR System"
        description NVARCHAR(500) NULL,

        -- Connection Details
        db_type NVARCHAR(50) NOT NULL,  -- mssql, postgresql, mysql, sqlite
        host NVARCHAR(255) NOT NULL,
        port INT NOT NULL,
        database_name NVARCHAR(255) NOT NULL,
        username NVARCHAR(255) NOT NULL,
        password_encrypted NVARCHAR(MAX) NOT NULL,  -- Encrypted with Fernet

        -- Connection Options
        use_ssl BIT DEFAULT 0,
        ssl_certificate NVARCHAR(MAX) NULL,
        connection_timeout INT DEFAULT 30,
        query_timeout INT DEFAULT 60,

        -- Schema Analysis Status
        is_active BIT DEFAULT 1,
        schema_analyzed BIT DEFAULT 0,
        analysis_status NVARCHAR(50) DEFAULT 'pending',  -- pending, analyzing, completed, failed
        analysis_error NVARCHAR(MAX) NULL,
        last_analysis_at DATETIME2 NULL,

        -- Auto-Detected Information
        detected_organization_type NVARCHAR(100) NULL,
        detected_modules NVARCHAR(MAX) NULL,  -- JSON array
        table_count INT DEFAULT 0,
        view_count INT DEFAULT 0,

        -- Sync Settings
        auto_sync_enabled BIT DEFAULT 0,
        sync_interval_hours INT DEFAULT 24,
        last_sync_at DATETIME2 NULL,

        -- ChromaDB Collection IDs
        schema_collection_id NVARCHAR(255) NULL,
        fewshot_collection_id NVARCHAR(255) NULL,

        -- Metadata
        created_at DATETIME2 DEFAULT GETUTCDATE(),
        updated_at DATETIME2 DEFAULT GETUTCDATE(),
        created_by UNIQUEIDENTIFIER NULL,

        -- Constraints
        CONSTRAINT FK_tenant_databases_tenant FOREIGN KEY (tenant_id)
            REFERENCES dbo.tenants(id) ON DELETE CASCADE,
        CONSTRAINT FK_tenant_databases_created_by FOREIGN KEY (created_by)
            REFERENCES dbo.tenant_users(id),
        CONSTRAINT CHK_tenant_databases_db_type CHECK (db_type IN ('mssql', 'postgresql', 'mysql', 'sqlite', 'oracle')),
        CONSTRAINT CHK_tenant_databases_status CHECK (analysis_status IN ('pending', 'analyzing', 'completed', 'failed'))
    );

    -- Create indexes
    CREATE INDEX IX_tenant_databases_tenant_id ON dbo.tenant_databases(tenant_id);
    CREATE INDEX IX_tenant_databases_is_active ON dbo.tenant_databases(is_active);
    CREATE INDEX IX_tenant_databases_analysis_status ON dbo.tenant_databases(analysis_status);

    PRINT 'Table dbo.tenant_databases created successfully.';
END
GO

-- ============================================================================
-- TABLE: schema_cache
-- Description: Auto-discovered schema metadata for each tenant database
-- ============================================================================

IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'dbo.schema_cache') AND type = 'U')
BEGIN
    CREATE TABLE dbo.schema_cache (
        -- Primary Key
        id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),

        -- Database Relationship
        tenant_db_id UNIQUEIDENTIFIER NOT NULL,

        -- Table Information
        table_name NVARCHAR(255) NOT NULL,
        schema_name NVARCHAR(128) DEFAULT 'dbo',
        table_type NVARCHAR(50) DEFAULT 'table',  -- table, view

        -- Column Information (JSON)
        column_info NVARCHAR(MAX) NOT NULL,  -- [{name, type, nullable, pk, fk, default}]

        -- Sample Data (JSON)
        sample_data NVARCHAR(MAX) NULL,  -- 5 sample rows

        -- Statistics
        row_count BIGINT DEFAULT 0,
        column_count INT DEFAULT 0,

        -- LLM-Generated Descriptions
        llm_description NVARCHAR(MAX) NULL,  -- Auto-generated description
        llm_purpose NVARCHAR(500) NULL,  -- What this table is for

        -- Module Detection
        detected_module NVARCHAR(100) NULL,  -- e.g., "Student Management"
        confidence_score DECIMAL(5,4) NULL,  -- 0.0000 to 1.0000

        -- Relationships
        foreign_keys NVARCHAR(MAX) NULL,  -- JSON: FK relationships
        referenced_by NVARCHAR(MAX) NULL,  -- JSON: Tables that reference this

        -- Metadata
        created_at DATETIME2 DEFAULT GETUTCDATE(),
        updated_at DATETIME2 DEFAULT GETUTCDATE(),

        -- Constraints
        CONSTRAINT FK_schema_cache_tenant_db FOREIGN KEY (tenant_db_id)
            REFERENCES dbo.tenant_databases(id) ON DELETE CASCADE,
        CONSTRAINT UQ_schema_cache_table UNIQUE (tenant_db_id, schema_name, table_name)
    );

    -- Create indexes
    CREATE INDEX IX_schema_cache_tenant_db_id ON dbo.schema_cache(tenant_db_id);
    CREATE INDEX IX_schema_cache_table_name ON dbo.schema_cache(table_name);
    CREATE INDEX IX_schema_cache_detected_module ON dbo.schema_cache(detected_module);

    PRINT 'Table dbo.schema_cache created successfully.';
END
GO

-- ============================================================================
-- TABLE: few_shot_examples
-- Description: Auto-generated Q&A pairs for SQL generation
-- ============================================================================

IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'dbo.few_shot_examples') AND type = 'U')
BEGIN
    CREATE TABLE dbo.few_shot_examples (
        -- Primary Key
        id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),

        -- Database Relationship
        tenant_db_id UNIQUEIDENTIFIER NOT NULL,

        -- Q&A Content
        question NVARCHAR(MAX) NOT NULL,
        sql_query NVARCHAR(MAX) NOT NULL,
        explanation NVARCHAR(MAX) NULL,

        -- Categorization
        module NVARCHAR(100) NULL,  -- e.g., "Employee Management"
        category NVARCHAR(100) NULL,  -- e.g., "count_query", "list_query"
        complexity NVARCHAR(20) DEFAULT 'medium',  -- simple, medium, complex

        -- Tables Used (JSON array)
        tables_used NVARCHAR(MAX) NULL,

        -- Quality & Status
        is_verified BIT DEFAULT 0,
        is_active BIT DEFAULT 1,
        quality_score DECIMAL(5,4) NULL,  -- 0.0000 to 1.0000

        -- Vector Embedding Reference
        embedding_id NVARCHAR(255) NULL,  -- ChromaDB document ID

        -- Usage Tracking
        usage_count INT DEFAULT 0,
        success_count INT DEFAULT 0,
        failure_count INT DEFAULT 0,
        last_used_at DATETIME2 NULL,

        -- Generation Source
        source NVARCHAR(50) DEFAULT 'auto',  -- auto, manual, imported
        generated_by NVARCHAR(100) NULL,  -- LLM model name

        -- Metadata
        created_at DATETIME2 DEFAULT GETUTCDATE(),
        updated_at DATETIME2 DEFAULT GETUTCDATE(),

        -- Constraints
        CONSTRAINT FK_few_shot_examples_tenant_db FOREIGN KEY (tenant_db_id)
            REFERENCES dbo.tenant_databases(id) ON DELETE CASCADE,
        CONSTRAINT CHK_few_shot_examples_complexity CHECK (complexity IN ('simple', 'medium', 'complex')),
        CONSTRAINT CHK_few_shot_examples_source CHECK (source IN ('auto', 'manual', 'imported'))
    );

    -- Create indexes
    CREATE INDEX IX_few_shot_examples_tenant_db_id ON dbo.few_shot_examples(tenant_db_id);
    CREATE INDEX IX_few_shot_examples_module ON dbo.few_shot_examples(module);
    CREATE INDEX IX_few_shot_examples_is_active ON dbo.few_shot_examples(is_active);
    CREATE INDEX IX_few_shot_examples_complexity ON dbo.few_shot_examples(complexity);

    PRINT 'Table dbo.few_shot_examples created successfully.';
END
GO

-- ============================================================================
-- TABLE: usage_metrics
-- Description: Daily usage tracking per tenant
-- ============================================================================

IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'dbo.usage_metrics') AND type = 'U')
BEGIN
    CREATE TABLE dbo.usage_metrics (
        -- Primary Key
        id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),

        -- Tenant Relationship
        tenant_id UNIQUEIDENTIFIER NOT NULL,

        -- Time Period
        metric_date DATE NOT NULL,

        -- Query Metrics
        total_queries INT DEFAULT 0,
        successful_queries INT DEFAULT 0,
        failed_queries INT DEFAULT 0,

        -- Token Usage
        total_tokens_used BIGINT DEFAULT 0,
        input_tokens BIGINT DEFAULT 0,
        output_tokens BIGINT DEFAULT 0,

        -- Performance
        avg_response_time_ms INT NULL,
        max_response_time_ms INT NULL,

        -- Feature Usage
        sql_queries INT DEFAULT 0,
        reports_generated INT DEFAULT 0,
        emails_sent INT DEFAULT 0,
        actions_executed INT DEFAULT 0,

        -- User Activity
        active_users INT DEFAULT 0,
        unique_sessions INT DEFAULT 0,

        -- Storage
        storage_used_mb DECIMAL(10,2) DEFAULT 0,

        -- Metadata
        created_at DATETIME2 DEFAULT GETUTCDATE(),
        updated_at DATETIME2 DEFAULT GETUTCDATE(),

        -- Constraints
        CONSTRAINT FK_usage_metrics_tenant FOREIGN KEY (tenant_id)
            REFERENCES dbo.tenants(id) ON DELETE CASCADE,
        CONSTRAINT UQ_usage_metrics_tenant_date UNIQUE (tenant_id, metric_date)
    );

    -- Create indexes
    CREATE INDEX IX_usage_metrics_tenant_id ON dbo.usage_metrics(tenant_id);
    CREATE INDEX IX_usage_metrics_metric_date ON dbo.usage_metrics(metric_date);

    PRINT 'Table dbo.usage_metrics created successfully.';
END
GO

-- ============================================================================
-- TABLE: audit_logs
-- Description: Security and compliance audit trail
-- ============================================================================

IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'dbo.audit_logs') AND type = 'U')
BEGIN
    CREATE TABLE dbo.audit_logs (
        -- Primary Key
        id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),

        -- Context
        tenant_id UNIQUEIDENTIFIER NULL,  -- NULL for platform-level events
        user_id UNIQUEIDENTIFIER NULL,

        -- Event Details
        event_type NVARCHAR(100) NOT NULL,  -- login, query, action, config_change
        event_action NVARCHAR(100) NOT NULL,  -- create, read, update, delete, execute
        resource_type NVARCHAR(100) NULL,  -- user, database, report, etc.
        resource_id NVARCHAR(255) NULL,

        -- Request Information
        request_id NVARCHAR(100) NULL,
        ip_address NVARCHAR(50) NULL,
        user_agent NVARCHAR(500) NULL,

        -- Event Data
        description NVARCHAR(MAX) NULL,
        old_value NVARCHAR(MAX) NULL,  -- JSON: previous state
        new_value NVARCHAR(MAX) NULL,  -- JSON: new state

        -- SQL Query (if applicable)
        sql_query NVARCHAR(MAX) NULL,
        query_duration_ms INT NULL,
        rows_affected INT NULL,

        -- Status
        status NVARCHAR(50) DEFAULT 'success',  -- success, failure, error
        error_message NVARCHAR(MAX) NULL,

        -- Metadata
        created_at DATETIME2 DEFAULT GETUTCDATE(),

        -- Constraints
        CONSTRAINT FK_audit_logs_tenant FOREIGN KEY (tenant_id)
            REFERENCES dbo.tenants(id) ON DELETE SET NULL,
        CONSTRAINT FK_audit_logs_user FOREIGN KEY (user_id)
            REFERENCES dbo.tenant_users(id) ON DELETE SET NULL
    );

    -- Create indexes
    CREATE INDEX IX_audit_logs_tenant_id ON dbo.audit_logs(tenant_id);
    CREATE INDEX IX_audit_logs_user_id ON dbo.audit_logs(user_id);
    CREATE INDEX IX_audit_logs_event_type ON dbo.audit_logs(event_type);
    CREATE INDEX IX_audit_logs_created_at ON dbo.audit_logs(created_at);
    CREATE INDEX IX_audit_logs_resource ON dbo.audit_logs(resource_type, resource_id);

    PRINT 'Table dbo.audit_logs created successfully.';
END
GO

-- ============================================================================
-- TABLE: api_keys
-- Description: API key management for programmatic access
-- ============================================================================

IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'dbo.api_keys') AND type = 'U')
BEGIN
    CREATE TABLE dbo.api_keys (
        -- Primary Key
        id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),

        -- Ownership
        tenant_id UNIQUEIDENTIFIER NOT NULL,
        user_id UNIQUEIDENTIFIER NOT NULL,

        -- Key Details
        name NVARCHAR(255) NOT NULL,  -- e.g., "Production API Key"
        key_prefix NVARCHAR(10) NOT NULL,  -- First 8 chars for identification
        key_hash NVARCHAR(255) NOT NULL,  -- SHA-256 hash of full key

        -- Permissions
        scopes NVARCHAR(MAX) NULL,  -- JSON: ["read", "write", "admin"]

        -- Limits
        rate_limit_per_minute INT DEFAULT 60,
        rate_limit_per_day INT DEFAULT 10000,

        -- Status
        is_active BIT DEFAULT 1,
        expires_at DATETIME2 NULL,

        -- Usage Tracking
        last_used_at DATETIME2 NULL,
        last_used_ip NVARCHAR(50) NULL,
        total_requests BIGINT DEFAULT 0,

        -- Metadata
        created_at DATETIME2 DEFAULT GETUTCDATE(),
        revoked_at DATETIME2 NULL,
        revoked_reason NVARCHAR(500) NULL,

        -- Constraints
        CONSTRAINT FK_api_keys_tenant FOREIGN KEY (tenant_id)
            REFERENCES dbo.tenants(id) ON DELETE CASCADE,
        CONSTRAINT FK_api_keys_user FOREIGN KEY (user_id)
            REFERENCES dbo.tenant_users(id)
    );

    -- Create indexes
    CREATE INDEX IX_api_keys_tenant_id ON dbo.api_keys(tenant_id);
    CREATE INDEX IX_api_keys_key_prefix ON dbo.api_keys(key_prefix);
    CREATE INDEX IX_api_keys_is_active ON dbo.api_keys(is_active);

    PRINT 'Table dbo.api_keys created successfully.';
END
GO

-- ============================================================================
-- TABLE: refresh_tokens
-- Description: JWT refresh token storage
-- ============================================================================

IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'dbo.refresh_tokens') AND type = 'U')
BEGIN
    CREATE TABLE dbo.refresh_tokens (
        -- Primary Key
        id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),

        -- User Relationship
        user_id UNIQUEIDENTIFIER NOT NULL,

        -- Token Details
        token_hash NVARCHAR(255) NOT NULL,  -- SHA-256 hash
        device_info NVARCHAR(500) NULL,
        ip_address NVARCHAR(50) NULL,

        -- Validity
        expires_at DATETIME2 NOT NULL,
        is_revoked BIT DEFAULT 0,
        revoked_at DATETIME2 NULL,

        -- Metadata
        created_at DATETIME2 DEFAULT GETUTCDATE(),

        -- Constraints
        CONSTRAINT FK_refresh_tokens_user FOREIGN KEY (user_id)
            REFERENCES dbo.tenant_users(id) ON DELETE CASCADE
    );

    -- Create indexes
    CREATE INDEX IX_refresh_tokens_user_id ON dbo.refresh_tokens(user_id);
    CREATE INDEX IX_refresh_tokens_token_hash ON dbo.refresh_tokens(token_hash);
    CREATE INDEX IX_refresh_tokens_expires_at ON dbo.refresh_tokens(expires_at);

    PRINT 'Table dbo.refresh_tokens created successfully.';
END
GO

-- ============================================================================
-- TRIGGERS: Auto-update updated_at timestamps
-- ============================================================================

-- Trigger for tenants
IF NOT EXISTS (SELECT * FROM sys.triggers WHERE name = 'TR_tenants_updated_at')
BEGIN
    EXEC('
    CREATE TRIGGER TR_tenants_updated_at ON dbo.tenants
    AFTER UPDATE AS
    BEGIN
        SET NOCOUNT ON;
        UPDATE dbo.tenants
        SET updated_at = GETUTCDATE()
        FROM dbo.tenants t
        INNER JOIN inserted i ON t.id = i.id;
    END
    ');
    PRINT 'Trigger TR_tenants_updated_at created.';
END
GO

-- Trigger for tenant_users
IF NOT EXISTS (SELECT * FROM sys.triggers WHERE name = 'TR_tenant_users_updated_at')
BEGIN
    EXEC('
    CREATE TRIGGER TR_tenant_users_updated_at ON dbo.tenant_users
    AFTER UPDATE AS
    BEGIN
        SET NOCOUNT ON;
        UPDATE dbo.tenant_users
        SET updated_at = GETUTCDATE()
        FROM dbo.tenant_users t
        INNER JOIN inserted i ON t.id = i.id;
    END
    ');
    PRINT 'Trigger TR_tenant_users_updated_at created.';
END
GO

-- Trigger for tenant_databases
IF NOT EXISTS (SELECT * FROM sys.triggers WHERE name = 'TR_tenant_databases_updated_at')
BEGIN
    EXEC('
    CREATE TRIGGER TR_tenant_databases_updated_at ON dbo.tenant_databases
    AFTER UPDATE AS
    BEGIN
        SET NOCOUNT ON;
        UPDATE dbo.tenant_databases
        SET updated_at = GETUTCDATE()
        FROM dbo.tenant_databases t
        INNER JOIN inserted i ON t.id = i.id;
    END
    ');
    PRINT 'Trigger TR_tenant_databases_updated_at created.';
END
GO

-- ============================================================================
-- STORED PROCEDURES
-- ============================================================================

-- Procedure to get tenant usage summary
IF NOT EXISTS (SELECT * FROM sys.procedures WHERE name = 'sp_GetTenantUsageSummary')
BEGIN
    EXEC('
    CREATE PROCEDURE dbo.sp_GetTenantUsageSummary
        @TenantId UNIQUEIDENTIFIER,
        @StartDate DATE = NULL,
        @EndDate DATE = NULL
    AS
    BEGIN
        SET NOCOUNT ON;

        -- Default to current month if dates not provided
        SET @StartDate = ISNULL(@StartDate, DATEADD(DAY, 1-DAY(GETDATE()), CAST(GETDATE() AS DATE)));
        SET @EndDate = ISNULL(@EndDate, CAST(GETDATE() AS DATE));

        SELECT
            @TenantId AS tenant_id,
            @StartDate AS period_start,
            @EndDate AS period_end,
            SUM(total_queries) AS total_queries,
            SUM(successful_queries) AS successful_queries,
            SUM(failed_queries) AS failed_queries,
            SUM(total_tokens_used) AS total_tokens_used,
            AVG(avg_response_time_ms) AS avg_response_time_ms,
            SUM(reports_generated) AS reports_generated,
            SUM(emails_sent) AS emails_sent,
            MAX(active_users) AS peak_active_users
        FROM dbo.usage_metrics
        WHERE tenant_id = @TenantId
          AND metric_date BETWEEN @StartDate AND @EndDate;
    END
    ');
    PRINT 'Stored procedure sp_GetTenantUsageSummary created.';
END
GO

-- ============================================================================
-- INITIAL DATA
-- ============================================================================

-- Note: No initial data inserted here.
-- First tenant will be created through the application registration flow.

PRINT '';
PRINT '================================================================================';
PRINT 'OryggiAI Platform Database schema created successfully!';
PRINT '================================================================================';
PRINT '';
PRINT 'Tables created:';
PRINT '  - dbo.tenants';
PRINT '  - dbo.tenant_users';
PRINT '  - dbo.tenant_databases';
PRINT '  - dbo.schema_cache';
PRINT '  - dbo.few_shot_examples';
PRINT '  - dbo.usage_metrics';
PRINT '  - dbo.audit_logs';
PRINT '  - dbo.api_keys';
PRINT '  - dbo.refresh_tokens';
PRINT '';
PRINT 'Next steps:';
PRINT '  1. Update PLATFORM_DB_* environment variables in .env';
PRINT '  2. Run the application to test connectivity';
PRINT '';
GO
