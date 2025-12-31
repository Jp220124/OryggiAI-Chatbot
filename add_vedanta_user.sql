USE OryggiVedanta;
GO
IF NOT EXISTS (SELECT * FROM sys.database_principals WHERE name = 'gateway_user')
BEGIN
    CREATE USER gateway_user FOR LOGIN gateway_user;
    EXEC sp_addrolemember 'db_datareader', 'gateway_user';
    PRINT 'User gateway_user added to OryggiVedanta';
END
ELSE
    PRINT 'User already exists';
GO
