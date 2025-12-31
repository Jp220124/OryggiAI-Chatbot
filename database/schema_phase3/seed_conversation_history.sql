-- =============================================
-- Phase 3: Conversation History Test Data
-- Purpose: Seed sample conversations for testing
-- =============================================

USE [HR_Chatbot];
GO

PRINT 'Seeding conversation history test data...';
GO

-- =============================================
-- Test Scenario 1: ADMIN User Multi-Session Conversations
-- =============================================

-- Session 1: Employee count query (admin_001)
INSERT INTO dbo.ConversationHistory (SessionId, UserId, UserRole, MessageType, MessageContent, ToolsUsed, DataReturned, SuccessFlag)
VALUES
    ('session_admin_001_20250114_001', 'admin_001', 'ADMIN', 'user', 'How many employees do we have?', NULL, NULL, 1),
    ('session_admin_001_20250114_001', 'admin_001', 'ADMIN', 'assistant', 'We have 150 employees in the database.',
     '["query_database"]', '{"result_count": 1, "sql_query": "SELECT COUNT(*) FROM Employees"}', 1);

-- Session 2: Department breakdown query (admin_001)
INSERT INTO dbo.ConversationHistory (SessionId, UserId, UserRole, MessageType, MessageContent, ToolsUsed, DataReturned, SuccessFlag)
VALUES
    ('session_admin_001_20250114_002', 'admin_001', 'ADMIN', 'user', 'Show me employee breakdown by department', NULL, NULL, 1),
    ('session_admin_001_20250114_002', 'admin_001', 'ADMIN', 'assistant',
     'Here is the employee breakdown by department:\n- IT: 40 employees\n- Finance: 30 employees\n- Sales: 35 employees\n- HR: 25 employees\n- Operations: 20 employees',
     '["query_database"]', '{"result_count": 5, "sql_query": "SELECT Department, COUNT(*) FROM Employees GROUP BY Department"}', 1);

PRINT 'ADMIN test conversations seeded (2 sessions, 4 messages).';
GO

-- =============================================
-- Test Scenario 2: HR_MANAGER User (Department-Scoped)
-- =============================================

-- Session 1: IT Manager viewing IT employees (manager_001)
INSERT INTO dbo.ConversationHistory (SessionId, UserId, UserRole, MessageType, MessageContent, ToolsUsed, DataReturned, SuccessFlag)
VALUES
    ('session_manager_001_20250114_001', 'manager_001', 'HR_MANAGER', 'user', 'List all employees in my department', NULL, NULL, 1),
    ('session_manager_001_20250114_001', 'manager_001', 'HR_MANAGER', 'assistant',
     'Found 40 employees in the IT department.',
     '["query_database"]', '{"result_count": 40, "sql_query": "SELECT * FROM Employees WHERE Department = ''IT''", "data_scoped": true}', 1);

-- Session 2: IT Manager checking salaries (manager_001)
INSERT INTO dbo.ConversationHistory (SessionId, UserId, UserRole, MessageType, MessageContent, ToolsUsed, DataReturned, SuccessFlag)
VALUES
    ('session_manager_001_20250114_002', 'manager_001', 'HR_MANAGER', 'user', 'What is the average salary in my department?', NULL, NULL, 1),
    ('session_manager_001_20250114_002', 'manager_001', 'HR_MANAGER', 'assistant',
     'The average salary in the IT department is $85,000.',
     '["query_database"]', '{"result_count": 1, "sql_query": "SELECT AVG(Salary) FROM Employees WHERE Department = ''IT''", "data_scoped": true}', 1);

-- Session 3: Finance Manager (manager_002)
INSERT INTO dbo.ConversationHistory (SessionId, UserId, UserRole, MessageType, MessageContent, ToolsUsed, DataReturned, SuccessFlag)
VALUES
    ('session_manager_002_20250114_001', 'manager_002', 'HR_MANAGER', 'user', 'Show me all Finance department employees', NULL, NULL, 1),
    ('session_manager_002_20250114_001', 'manager_002', 'HR_MANAGER', 'assistant',
     'Found 30 employees in the Finance department.',
     '["query_database"]', '{"result_count": 30, "sql_query": "SELECT * FROM Employees WHERE Department = ''Finance''", "data_scoped": true}', 1);

PRINT 'HR_MANAGER test conversations seeded (3 sessions, 6 messages).';
GO

-- =============================================
-- Test Scenario 3: HR_STAFF User (User-Scoped)
-- =============================================

-- Session 1: Staff viewing own details (staff_001)
INSERT INTO dbo.ConversationHistory (SessionId, UserId, UserRole, MessageType, MessageContent, ToolsUsed, DataReturned, SuccessFlag)
VALUES
    ('session_staff_001_20250114_001', 'staff_001', 'HR_STAFF', 'user', 'Show my employee details', NULL, NULL, 1),
    ('session_staff_001_20250114_001', 'staff_001', 'HR_STAFF', 'assistant',
     'Your details:\n- EmployeeId: staff_001\n- Name: Jane Smith\n- Department: IT\n- Position: Developer\n- Salary: $75,000',
     '["query_database"]', '{"result_count": 1, "sql_query": "SELECT * FROM Employees WHERE EmployeeId = ''staff_001''", "data_scoped": true}', 1);

-- Session 2: Staff checking leave balance (staff_001)
INSERT INTO dbo.ConversationHistory (SessionId, UserId, UserRole, MessageType, MessageContent, ToolsUsed, DataReturned, SuccessFlag)
VALUES
    ('session_staff_001_20250114_002', 'staff_001', 'HR_STAFF', 'user', 'How many leave days do I have?', NULL, NULL, 1),
    ('session_staff_001_20250114_002', 'staff_001', 'HR_STAFF', 'assistant',
     'You have 15 leave days remaining.',
     '["query_database"]', '{"result_count": 1, "sql_query": "SELECT LeaveDaysRemaining FROM Employees WHERE EmployeeId = ''staff_001''", "data_scoped": true}', 1);

-- Session 3: Another staff member (staff_002)
INSERT INTO dbo.ConversationHistory (SessionId, UserId, UserRole, MessageType, MessageContent, ToolsUsed, DataReturned, SuccessFlag)
VALUES
    ('session_staff_002_20250114_001', 'staff_002', 'HR_STAFF', 'user', 'What is my current salary?', NULL, NULL, 1),
    ('session_staff_002_20250114_001', 'staff_002', 'HR_STAFF', 'assistant',
     'Your current salary is $68,000.',
     '["query_database"]', '{"result_count": 1, "sql_query": "SELECT Salary FROM Employees WHERE EmployeeId = ''staff_002''", "data_scoped": true}', 1);

PRINT 'HR_STAFF test conversations seeded (3 sessions, 6 messages).';
GO

-- =============================================
-- Test Scenario 4: VIEWER User (Read-Only, User-Scoped)
-- =============================================

-- Session 1: Viewer checking own info (viewer_001)
INSERT INTO dbo.ConversationHistory (SessionId, UserId, UserRole, MessageType, MessageContent, ToolsUsed, DataReturned, SuccessFlag)
VALUES
    ('session_viewer_001_20250114_001', 'viewer_001', 'VIEWER', 'user', 'Show my details', NULL, NULL, 1),
    ('session_viewer_001_20250114_001', 'viewer_001', 'VIEWER', 'assistant',
     'Your details:\n- EmployeeId: viewer_001\n- Name: Bob Viewer\n- Department: Sales\n- Position: Sales Representative',
     '["query_database"]', '{"result_count": 1, "sql_query": "SELECT * FROM Employees WHERE EmployeeId = ''viewer_001''", "data_scoped": true}', 1);

PRINT 'VIEWER test conversations seeded (1 session, 2 messages).';
GO

-- =============================================
-- Test Scenario 5: Error Scenarios
-- =============================================

-- Failed query (database error)
INSERT INTO dbo.ConversationHistory (SessionId, UserId, UserRole, MessageType, MessageContent, ToolsUsed, DataReturned, SuccessFlag)
VALUES
    ('session_admin_002_20250114_001', 'admin_002', 'ADMIN', 'user', 'Show me employee XYZ', NULL, NULL, 1),
    ('session_admin_002_20250114_001', 'admin_002', 'ADMIN', 'assistant',
     'Error: No employee found with ID XYZ.',
     '["query_database"]', '{"error": "No results found", "sql_query": "SELECT * FROM Employees WHERE EmployeeId = ''XYZ''"}', 0);

PRINT 'Error scenario seeded (1 session, 2 messages).';
GO

-- =============================================
-- Test Scenario 6: Multi-Turn Conversations
-- =============================================

-- Complex multi-turn conversation
INSERT INTO dbo.ConversationHistory (SessionId, UserId, UserRole, MessageType, MessageContent, ToolsUsed, DataReturned, SuccessFlag)
VALUES
    -- Turn 1
    ('session_manager_003_20250114_001', 'manager_003', 'HR_MANAGER', 'user', 'How many employees are in my department?', NULL, NULL, 1),
    ('session_manager_003_20250114_001', 'manager_003', 'HR_MANAGER', 'assistant',
     'There are 35 employees in the Sales department.',
     '["query_database"]', '{"result_count": 35, "data_scoped": true}', 1),

    -- Turn 2
    ('session_manager_003_20250114_001', 'manager_003', 'HR_MANAGER', 'user', 'What is their average age?', NULL, NULL, 1),
    ('session_manager_003_20250114_001', 'manager_003', 'HR_MANAGER', 'assistant',
     'The average age of employees in the Sales department is 32 years.',
     '["query_database"]', '{"result_count": 1, "data_scoped": true}', 1),

    -- Turn 3
    ('session_manager_003_20250114_001', 'manager_003', 'HR_MANAGER', 'user', 'How many joined in the last year?', NULL, NULL, 1),
    ('session_manager_003_20250114_001', 'manager_003', 'HR_MANAGER', 'assistant',
     '8 employees in the Sales department joined in the last year.',
     '["query_database"]', '{"result_count": 8, "data_scoped": true}', 1);

PRINT 'Multi-turn conversation seeded (1 session, 6 messages).';
GO

-- =============================================
-- Summary and Verification
-- =============================================

DECLARE @TotalMessages INT;
DECLARE @TotalSessions INT;
DECLARE @TotalUsers INT;

SELECT @TotalMessages = COUNT(*) FROM dbo.ConversationHistory;
SELECT @TotalSessions = COUNT(DISTINCT SessionId) FROM dbo.ConversationHistory;
SELECT @TotalUsers = COUNT(DISTINCT UserId) FROM dbo.ConversationHistory;

PRINT '';
PRINT '=============================================';
PRINT 'Seed Data Summary:';
PRINT '=============================================';
PRINT 'Total Messages: ' + CAST(@TotalMessages AS NVARCHAR);
PRINT 'Total Sessions: ' + CAST(@TotalSessions AS NVARCHAR);
PRINT 'Total Users: ' + CAST(@TotalUsers AS NVARCHAR);
PRINT '';
PRINT 'Breakdown by Role:';

SELECT
    UserRole,
    COUNT(*) AS MessageCount,
    COUNT(DISTINCT SessionId) AS SessionCount,
    COUNT(DISTINCT UserId) AS UserCount
FROM dbo.ConversationHistory
GROUP BY UserRole
ORDER BY
    CASE UserRole
        WHEN 'ADMIN' THEN 1
        WHEN 'HR_MANAGER' THEN 2
        WHEN 'HR_STAFF' THEN 3
        WHEN 'VIEWER' THEN 4
    END;

PRINT '';
PRINT 'Breakdown by MessageType:';

SELECT
    MessageType,
    COUNT(*) AS MessageCount
FROM dbo.ConversationHistory
GROUP BY MessageType;

PRINT '';
PRINT 'Success vs Failure:';

SELECT
    CASE SuccessFlag
        WHEN 1 THEN 'Success'
        WHEN 0 THEN 'Failure'
    END AS Status,
    COUNT(*) AS MessageCount
FROM dbo.ConversationHistory
GROUP BY SuccessFlag;

GO

PRINT '';
PRINT '=============================================';
PRINT 'Seed data created successfully!';
PRINT '=============================================';
PRINT '';
PRINT 'Test Queries:';
PRINT '-------------';
PRINT '1. View all conversations: SELECT * FROM dbo.ConversationHistory ORDER BY Timestamp;';
PRINT '2. View ADMIN conversations: SELECT * FROM dbo.ConversationHistory WHERE UserRole = ''ADMIN'';';
PRINT '3. View specific session: SELECT * FROM dbo.ConversationHistory WHERE SessionId = ''session_admin_001_20250114_001'' ORDER BY Timestamp;';
PRINT '4. View user history: SELECT * FROM dbo.ConversationHistory WHERE UserId = ''staff_001'' ORDER BY Timestamp;';
PRINT '';
GO
