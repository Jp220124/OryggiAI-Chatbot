-- Migration: Add query logging columns to gateway_query_logs table
-- Date: 2025-01-29
-- Description: Adds natural_language_question, llm_model, tokens_used, generation_time_ms columns
--              Also makes session_id nullable for direct API queries

-- Check if columns exist before adding
-- Add natural_language_question column
IF NOT EXISTS (
    SELECT * FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_NAME = 'gateway_query_logs'
    AND COLUMN_NAME = 'natural_language_question'
)
BEGIN
    ALTER TABLE gateway_query_logs
    ADD natural_language_question NVARCHAR(MAX) NULL;
    PRINT 'Added column: natural_language_question';
END
ELSE
BEGIN
    PRINT 'Column already exists: natural_language_question';
END
GO

-- Add llm_model column
IF NOT EXISTS (
    SELECT * FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_NAME = 'gateway_query_logs'
    AND COLUMN_NAME = 'llm_model'
)
BEGIN
    ALTER TABLE gateway_query_logs
    ADD llm_model NVARCHAR(100) NULL;
    PRINT 'Added column: llm_model';
END
ELSE
BEGIN
    PRINT 'Column already exists: llm_model';
END
GO

-- Add tokens_used column
IF NOT EXISTS (
    SELECT * FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_NAME = 'gateway_query_logs'
    AND COLUMN_NAME = 'tokens_used'
)
BEGIN
    ALTER TABLE gateway_query_logs
    ADD tokens_used INT NULL;
    PRINT 'Added column: tokens_used';
END
ELSE
BEGIN
    PRINT 'Column already exists: tokens_used';
END
GO

-- Add generation_time_ms column
IF NOT EXISTS (
    SELECT * FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_NAME = 'gateway_query_logs'
    AND COLUMN_NAME = 'generation_time_ms'
)
BEGIN
    ALTER TABLE gateway_query_logs
    ADD generation_time_ms INT NULL;
    PRINT 'Added column: generation_time_ms';
END
ELSE
BEGIN
    PRINT 'Column already exists: generation_time_ms';
END
GO

-- Make session_id nullable (for direct API queries without gateway)
-- Note: This requires dropping and recreating the foreign key constraint
IF EXISTS (
    SELECT * FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_NAME = 'gateway_query_logs'
    AND COLUMN_NAME = 'session_id'
    AND IS_NULLABLE = 'NO'
)
BEGIN
    -- First drop the foreign key if it exists
    DECLARE @constraintName NVARCHAR(256);
    SELECT @constraintName = name
    FROM sys.foreign_keys
    WHERE parent_object_id = OBJECT_ID('gateway_query_logs')
    AND OBJECT_NAME(referenced_object_id) = 'gateway_sessions'
    AND COL_NAME(parent_object_id, parent_column_id) = 'session_id';

    IF @constraintName IS NOT NULL
    BEGIN
        DECLARE @dropFK NVARCHAR(500) = 'ALTER TABLE gateway_query_logs DROP CONSTRAINT ' + @constraintName;
        EXEC sp_executesql @dropFK;
        PRINT 'Dropped foreign key constraint: ' + @constraintName;
    END

    -- Make session_id nullable
    ALTER TABLE gateway_query_logs
    ALTER COLUMN session_id UNIQUEIDENTIFIER NULL;
    PRINT 'Made session_id nullable';

    -- Recreate the foreign key with CASCADE delete
    ALTER TABLE gateway_query_logs
    ADD CONSTRAINT FK_gateway_query_logs_session_id
    FOREIGN KEY (session_id) REFERENCES gateway_sessions(id) ON DELETE CASCADE;
    PRINT 'Recreated foreign key constraint with CASCADE delete';
END
ELSE
BEGIN
    PRINT 'Column session_id is already nullable or does not exist';
END
GO

-- Verify the changes
SELECT
    COLUMN_NAME,
    DATA_TYPE,
    IS_NULLABLE,
    CHARACTER_MAXIMUM_LENGTH
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_NAME = 'gateway_query_logs'
ORDER BY ORDINAL_POSITION;
GO

PRINT '=== Migration completed successfully ===';
GO
