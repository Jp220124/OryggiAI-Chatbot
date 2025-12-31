-- =============================================
-- Phase 3: Conversation History Table
-- Purpose: Store all chatbot conversation messages
-- Features: Session tracking, RBAC integration, soft deletion
-- =============================================

USE [HR_Chatbot];
GO

-- Drop existing table if it exists (for development)
IF OBJECT_ID('dbo.ConversationHistory', 'U') IS NOT NULL
BEGIN
    DROP TABLE dbo.ConversationHistory;
    PRINT 'Existing ConversationHistory table dropped.';
END
GO

-- Create ConversationHistory table
CREATE TABLE dbo.ConversationHistory (
    -- Primary Key
    ConversationId INT IDENTITY(1,1) PRIMARY KEY,

    -- Session Management
    SessionId NVARCHAR(100) NOT NULL,

    -- User Information (RBAC Integration)
    UserId NVARCHAR(50) NOT NULL,
    UserRole NVARCHAR(20) NOT NULL,

    -- Message Details
    MessageType NVARCHAR(10) NOT NULL
        CHECK (MessageType IN ('user', 'assistant')),
    MessageContent NVARCHAR(MAX) NOT NULL,

    -- Tool Execution Context (JSON format)
    ToolsUsed NVARCHAR(MAX) NULL,  -- JSON array of tool names
    DataReturned NVARCHAR(MAX) NULL,  -- JSON object of results

    -- Status Tracking
    SuccessFlag BIT NOT NULL DEFAULT 1,

    -- Timestamps
    Timestamp DATETIME2 NOT NULL DEFAULT GETUTCDATE(),

    -- Soft Deletion
    IsActive BIT NOT NULL DEFAULT 1,

    -- Foreign Key to UserRoles
    CONSTRAINT FK_ConversationHistory_UserRoles
        FOREIGN KEY (UserId) REFERENCES dbo.UserRoles(UserId)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);
GO

PRINT 'ConversationHistory table created successfully.';
GO

-- =============================================
-- Create Indexes for Performance
-- =============================================

-- Index 1: User-based queries (most common use case)
-- Used for: Retrieving user's conversation history
CREATE NONCLUSTERED INDEX IX_ConversationHistory_UserId
    ON dbo.ConversationHistory(UserId, Timestamp DESC)
    WHERE IsActive = 1
    INCLUDE (SessionId, MessageType, MessageContent);
GO

PRINT 'Index IX_ConversationHistory_UserId created.';
GO

-- Index 2: Session-based queries
-- Used for: Retrieving complete conversation sessions
CREATE NONCLUSTERED INDEX IX_ConversationHistory_SessionId
    ON dbo.ConversationHistory(SessionId, Timestamp ASC)
    WHERE IsActive = 1
    INCLUDE (UserId, MessageType, MessageContent);
GO

PRINT 'Index IX_ConversationHistory_SessionId created.';
GO

-- Index 3: Time-based queries
-- Used for: Recent conversations, analytics
CREATE NONCLUSTERED INDEX IX_ConversationHistory_Timestamp
    ON dbo.ConversationHistory(Timestamp DESC)
    WHERE IsActive = 1
    INCLUDE (UserId, SessionId, MessageType);
GO

PRINT 'Index IX_ConversationHistory_Timestamp created.';
GO

-- Index 4: User-Role filtering
-- Used for: Role-based analytics and reporting
CREATE NONCLUSTERED INDEX IX_ConversationHistory_UserRole
    ON dbo.ConversationHistory(UserRole, Timestamp DESC)
    WHERE IsActive = 1;
GO

PRINT 'Index IX_ConversationHistory_UserRole created.';
GO

-- =============================================
-- Create ConversationEmbeddings Table
-- Purpose: Store embeddings for semantic search
-- =============================================

IF OBJECT_ID('dbo.ConversationEmbeddings', 'U') IS NOT NULL
BEGIN
    DROP TABLE dbo.ConversationEmbeddings;
    PRINT 'Existing ConversationEmbeddings table dropped.';
END
GO

CREATE TABLE dbo.ConversationEmbeddings (
    -- Primary Key
    EmbeddingId INT IDENTITY(1,1) PRIMARY KEY,

    -- Link to Conversation
    ConversationId INT NOT NULL,

    -- User Information (for RBAC filtering)
    UserId NVARCHAR(50) NOT NULL,

    -- Session Context
    SessionId NVARCHAR(100) NOT NULL,

    -- Text Being Embedded (combined user + assistant messages)
    TextContent NVARCHAR(MAX) NOT NULL,

    -- ChromaDB Reference
    ChromaDocId NVARCHAR(100) NOT NULL UNIQUE,  -- UUID from ChromaDB

    -- Metadata for Retrieval
    MessageCount INT NOT NULL DEFAULT 1,  -- How many messages in this chunk

    -- Timestamps
    CreatedAt DATETIME2 NOT NULL DEFAULT GETUTCDATE(),

    -- Foreign Keys
    CONSTRAINT FK_ConversationEmbeddings_Conversation
        FOREIGN KEY (ConversationId) REFERENCES dbo.ConversationHistory(ConversationId)
        ON DELETE CASCADE,

    CONSTRAINT FK_ConversationEmbeddings_UserRoles
        FOREIGN KEY (UserId) REFERENCES dbo.UserRoles(UserId)
        ON DELETE CASCADE
);
GO

PRINT 'ConversationEmbeddings table created successfully.';
GO

-- Index for user-based embedding lookup
CREATE NONCLUSTERED INDEX IX_ConversationEmbeddings_UserId
    ON dbo.ConversationEmbeddings(UserId, CreatedAt DESC);
GO

-- Index for session-based embedding lookup
CREATE NONCLUSTERED INDEX IX_ConversationEmbeddings_SessionId
    ON dbo.ConversationEmbeddings(SessionId);
GO

PRINT 'ConversationEmbeddings indexes created.';
GO

-- =============================================
-- Sample Data Verification Queries
-- =============================================

PRINT '';
PRINT 'Database schema created successfully!';
PRINT '';
PRINT 'Verification Queries:';
PRINT '--------------------';
PRINT '1. Check table structure:';
PRINT '   SELECT * FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = ''ConversationHistory'';';
PRINT '';
PRINT '2. Check indexes:';
PRINT '   SELECT * FROM sys.indexes WHERE object_id = OBJECT_ID(''dbo.ConversationHistory'');';
PRINT '';
PRINT '3. Check foreign keys:';
PRINT '   SELECT * FROM INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS WHERE CONSTRAINT_NAME LIKE ''%ConversationHistory%'';';
PRINT '';
PRINT 'Next Steps:';
PRINT '-----------';
PRINT '1. Run this script: sqlcmd -S localhost -d HR_Chatbot -i create_conversation_history.sql';
PRINT '2. Seed test data: sqlcmd -S localhost -d HR_Chatbot -i seed_conversation_history.sql';
PRINT '3. Test with Python: python -m tests.test_conversation_store';
GO
