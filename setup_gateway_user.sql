-- Enable mixed mode authentication
EXEC xp_instance_regwrite N'HKEY_LOCAL_MACHINE', N'Software\Microsoft\MSSQLServer\MSSQLServer', N'LoginMode', REG_DWORD, 2;

-- Create gateway_user login if not exists
IF NOT EXISTS (SELECT * FROM sys.server_principals WHERE name = 'gateway_user')
BEGIN
    CREATE LOGIN gateway_user WITH PASSWORD = 'Gateway@123!', CHECK_POLICY = OFF;
    PRINT 'Login gateway_user created';
END
ELSE
    PRINT 'Login gateway_user already exists';

-- Grant access to OryggiAI_Cloud database
USE OryggiAI_Cloud;
IF NOT EXISTS (SELECT * FROM sys.database_principals WHERE name = 'gateway_user')
BEGIN
    CREATE USER gateway_user FOR LOGIN gateway_user;
    EXEC sp_addrolemember 'db_datareader', 'gateway_user';
    PRINT 'User gateway_user added to OryggiAI_Cloud';
END
ELSE
    PRINT 'User gateway_user already exists in database';
GO
