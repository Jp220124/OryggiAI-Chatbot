-- Platform Database Tables for Gateway Testing

USE OryggiAI_Platform;
GO

-- Create tenants table
CREATE TABLE tenants (
    id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    name NVARCHAR(255) NOT NULL,
    slug NVARCHAR(100) NOT NULL UNIQUE,
    email NVARCHAR(255) NOT NULL UNIQUE,
    company_name NVARCHAR(255),
    [plan] NVARCHAR(50) DEFAULT 'FREE',
    is_active BIT DEFAULT 1,
    created_at DATETIME DEFAULT GETUTCDATE(),
    updated_at DATETIME DEFAULT GETUTCDATE()
);
GO

-- Create tenant_users table
CREATE TABLE tenant_users (
    id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    tenant_id UNIQUEIDENTIFIER NOT NULL,
    email NVARCHAR(255) NOT NULL,
    password_hash NVARCHAR(255),
    full_name NVARCHAR(255),
    role NVARCHAR(50) DEFAULT 'user',
    is_active BIT DEFAULT 1,
    email_verified BIT DEFAULT 0,
    created_at DATETIME DEFAULT GETUTCDATE(),
    updated_at DATETIME DEFAULT GETUTCDATE(),
    FOREIGN KEY (tenant_id) REFERENCES tenants(id)
);
GO

-- Create api_keys table
CREATE TABLE api_keys (
    id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    tenant_id UNIQUEIDENTIFIER NOT NULL,
    user_id UNIQUEIDENTIFIER NOT NULL,
    name NVARCHAR(255),
    key_prefix NVARCHAR(10),
    key_hash NVARCHAR(255),
    scopes NVARCHAR(MAX),
    is_active BIT DEFAULT 1,
    expires_at DATETIME,
    last_used_at DATETIME,
    revoked_at DATETIME,
    revoked_reason NVARCHAR(500),
    created_at DATETIME DEFAULT GETUTCDATE(),
    updated_at DATETIME DEFAULT GETUTCDATE(),
    FOREIGN KEY (tenant_id) REFERENCES tenants(id),
    FOREIGN KEY (user_id) REFERENCES tenant_users(id)
);
GO

-- Create tenant_databases table
CREATE TABLE tenant_databases (
    id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    tenant_id UNIQUEIDENTIFIER NOT NULL,
    name NVARCHAR(255) NOT NULL,
    db_type NVARCHAR(50) DEFAULT 'mssql',
    host NVARCHAR(255),
    port INT DEFAULT 1433,
    database_name NVARCHAR(255),
    username NVARCHAR(255),
    password_encrypted NVARCHAR(MAX),
    is_active BIT DEFAULT 1,
    connection_mode NVARCHAR(50) DEFAULT 'direct_only',
    gateway_connected BIT DEFAULT 0,
    gateway_api_key_id UNIQUEIDENTIFIER,
    created_at DATETIME DEFAULT GETUTCDATE(),
    updated_at DATETIME DEFAULT GETUTCDATE(),
    FOREIGN KEY (tenant_id) REFERENCES tenants(id),
    FOREIGN KEY (gateway_api_key_id) REFERENCES api_keys(id)
);
GO

PRINT 'Tables created successfully!';
