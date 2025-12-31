/*
=============================================================================
UserRoles Test Data Seeding
=============================================================================
Purpose: Populate UserRoles table with test users for each role type

Test Users:
  - ADMIN:      admin_001, admin_002
  - HR_MANAGER: manager_001 (IT), manager_002 (Finance), manager_003 (Sales)
  - HR_STAFF:   staff_001 (IT), staff_002 (Finance), staff_003 (Sales)
  - VIEWER:     viewer_001, viewer_002, viewer_003

Author: Phase 2 Implementation
Date: 2025-11-14
=============================================================================
*/

USE [Oryggi_HR_DB];
GO

PRINT 'Starting UserRoles test data seeding...';
GO

-- Clear existing test data (optional, for clean re-seeding)
DELETE FROM dbo.UserRoles
WHERE UserId LIKE 'admin_%'
   OR UserId LIKE 'manager_%'
   OR UserId LIKE 'staff_%'
   OR UserId LIKE 'viewer_%';
PRINT 'Cleared existing test data';
GO

-- ============================================================================
-- ADMIN Users (Role Level: 100)
-- Full system access, no data scoping restrictions
-- ============================================================================
INSERT INTO dbo.UserRoles (UserId, EmployeeId, Role, Department, AssignedBy)
VALUES
    ('admin_001', NULL, 'ADMIN', NULL, 'SYSTEM'),
    ('admin_002', NULL, 'ADMIN', NULL, 'SYSTEM');

PRINT 'Inserted 2 ADMIN users';
GO

-- ============================================================================
-- HR_MANAGER Users (Role Level: 50)
-- Department-level access, can see all employees in their department
-- ============================================================================
INSERT INTO dbo.UserRoles (UserId, EmployeeId, Role, Department, AssignedBy)
VALUES
    ('manager_001', NULL, 'HR_MANAGER', 'IT', 'admin_001'),
    ('manager_002', NULL, 'HR_MANAGER', 'Finance', 'admin_001'),
    ('manager_003', NULL, 'HR_MANAGER', 'Sales', 'admin_001'),
    ('manager_004', NULL, 'HR_MANAGER', 'HR', 'admin_001'),
    ('manager_005', NULL, 'HR_MANAGER', 'Operations', 'admin_001');

PRINT 'Inserted 5 HR_MANAGER users';
GO

-- ============================================================================
-- HR_STAFF Users (Role Level: 30)
-- Team-level access, can see own data + team data
-- ============================================================================
INSERT INTO dbo.UserRoles (UserId, EmployeeId, Role, Department, AssignedBy)
VALUES
    ('staff_001', NULL, 'HR_STAFF', 'IT', 'manager_001'),
    ('staff_002', NULL, 'HR_STAFF', 'Finance', 'manager_002'),
    ('staff_003', NULL, 'HR_STAFF', 'Sales', 'manager_003'),
    ('staff_004', NULL, 'HR_STAFF', 'HR', 'manager_004'),
    ('staff_005', NULL, 'HR_STAFF', 'Operations', 'manager_005'),
    ('staff_006', NULL, 'HR_STAFF', 'IT', 'manager_001'),
    ('staff_007', NULL, 'HR_STAFF', 'Finance', 'manager_002');

PRINT 'Inserted 7 HR_STAFF users';
GO

-- ============================================================================
-- VIEWER Users (Role Level: 10)
-- Read-only access, can only see own data
-- ============================================================================
INSERT INTO dbo.UserRoles (UserId, EmployeeId, Role, Department, AssignedBy)
VALUES
    ('viewer_001', NULL, 'VIEWER', NULL, 'manager_001'),
    ('viewer_002', NULL, 'VIEWER', NULL, 'manager_002'),
    ('viewer_003', NULL, 'VIEWER', NULL, 'manager_003'),
    ('viewer_004', NULL, 'VIEWER', NULL, 'admin_001'),
    ('viewer_005', NULL, 'VIEWER', NULL, 'admin_001');

PRINT 'Inserted 5 VIEWER users';
GO

-- ============================================================================
-- Link to Existing Employees (if Employees table has data)
-- ============================================================================
IF OBJECT_ID('dbo.Employees', 'U') IS NOT NULL
BEGIN
    PRINT 'Attempting to link UserRoles to existing Employees...';

    -- Update UserRoles with EmployeeId for matching employees
    -- This is a best-effort approach - will only link if employees exist

    UPDATE ur
    SET ur.EmployeeId = e.EmployeeId
    FROM dbo.UserRoles ur
    CROSS APPLY (
        SELECT TOP 1 EmployeeId
        FROM dbo.Employees e
        WHERE e.Department = ur.Department
          AND ur.EmployeeId IS NULL
        ORDER BY e.EmployeeId
    ) e
    WHERE ur.Role IN ('HR_STAFF', 'HR_MANAGER')
      AND ur.Department IS NOT NULL;

    PRINT 'Linked UserRoles to Employees where possible';
END
ELSE
BEGIN
    PRINT 'Employees table not found - skipping EmployeeId linking';
END
GO

-- ============================================================================
-- Verification Queries
-- ============================================================================
PRINT '';
PRINT '========================================';
PRINT 'UserRoles Seeding Summary';
PRINT '========================================';

SELECT
    Role,
    COUNT(*) AS UserCount,
    COUNT(DISTINCT Department) AS UniqueDepartments
FROM dbo.UserRoles
WHERE IsActive = 1
GROUP BY Role
ORDER BY
    CASE Role
        WHEN 'ADMIN' THEN 1
        WHEN 'HR_MANAGER' THEN 2
        WHEN 'HR_STAFF' THEN 3
        WHEN 'VIEWER' THEN 4
    END;

PRINT '';
PRINT 'Department Distribution:';
SELECT
    ISNULL(Department, 'N/A') AS Department,
    COUNT(*) AS UserCount
FROM dbo.UserRoles
WHERE IsActive = 1
GROUP BY Department
ORDER BY Department;

PRINT '';
PRINT 'Sample Users by Role:';
SELECT TOP 3
    UserId,
    Role,
    Department,
    AssignedBy,
    FORMAT(AssignedDate, 'yyyy-MM-dd HH:mm') AS AssignedDate
FROM dbo.UserRoles
WHERE IsActive = 1
  AND Role = 'ADMIN'
ORDER BY UserId;

SELECT TOP 3
    UserId,
    Role,
    Department,
    AssignedBy,
    FORMAT(AssignedDate, 'yyyy-MM-dd HH:mm') AS AssignedDate
FROM dbo.UserRoles
WHERE IsActive = 1
  AND Role = 'HR_MANAGER'
ORDER BY UserId;

SELECT TOP 3
    UserId,
    Role,
    Department,
    AssignedBy,
    FORMAT(AssignedDate, 'yyyy-MM-dd HH:mm') AS AssignedDate
FROM dbo.UserRoles
WHERE IsActive = 1
  AND Role = 'HR_STAFF'
ORDER BY UserId;

SELECT TOP 3
    UserId,
    Role,
    Department,
    AssignedBy,
    FORMAT(AssignedDate, 'yyyy-MM-dd HH:mm') AS AssignedDate
FROM dbo.UserRoles
WHERE IsActive = 1
  AND Role = 'VIEWER'
ORDER BY UserId;

PRINT '';
PRINT '========================================';
PRINT 'UserRoles seeding completed successfully!';
PRINT 'Total users created: 19';
PRINT '  - ADMIN:      2';
PRINT '  - HR_MANAGER: 5 (across 5 departments)';
PRINT '  - HR_STAFF:   7 (across 5 departments)';
PRINT '  - VIEWER:     5';
PRINT '========================================';
GO
