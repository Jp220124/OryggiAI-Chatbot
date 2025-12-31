-- Create test data for gateway testing
USE OryggiAI_Platform;
GO

-- Create a test tenant
DECLARE @tenant_id UNIQUEIDENTIFIER = NEWID();
DECLARE @user_id UNIQUEIDENTIFIER = NEWID();
DECLARE @db_id UNIQUEIDENTIFIER = NEWID();

INSERT INTO tenants (id, name, slug, email, company_name, [plan], is_active)
VALUES (@tenant_id, 'Test Company', 'test-company', 'test@example.com', 'Test Company Inc.', 'PROFESSIONAL', 1);

-- Create a test user (password: test123)
INSERT INTO tenant_users (id, tenant_id, email, password_hash, full_name, role, is_active, email_verified)
VALUES (@user_id, @tenant_id, 'test@example.com',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj/Awk.pJYMG', -- bcrypt hash of 'test123'
    'Test User', 'owner', 1, 1);

-- Create a test database entry (we'll use the local OryggiAI_Local database)
INSERT INTO tenant_databases (id, tenant_id, name, db_type, host, port, database_name, username, password_encrypted, is_active, connection_mode, gateway_connected)
VALUES (@db_id, @tenant_id, 'Local Test Database', 'mssql', 'localhost', 1433, 'OryggiAI_Local', 'test_user', 'encrypted_dummy', 1, 'gateway_only', 0);

-- Output the IDs for reference
SELECT 'Test data created!' as message;
SELECT @tenant_id as tenant_id, @user_id as user_id, @db_id as database_id;
