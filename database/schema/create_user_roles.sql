/*
=============================================================================
UserRoles Table Schema
=============================================================================
Purpose: Store user role assignments for RBAC system

Role Hierarchy:
  - ADMIN:      100 (Full system access)
  - HR_MANAGER:  50 (Department-level access)
  - HR_STAFF:    30 (Team-level access)
  - VIEWER:      10 (Read-only access)

Author: Phase 2 Implementation
Date: 2025-11-14
=============================================================================
*/

USE [Oryggi_HR_DB];
GO

-- Drop table if exists (for clean re-creation during development)
IF OBJECT_ID('dbo.UserRoles', 'U') IS NOT NULL
BEGIN
    PRINT 'Dropping existing UserRoles table...';
    DROP TABLE dbo.UserRoles;
END
GO

-- Create UserRoles table
CREATE TABLE dbo.UserRoles (
    -- Primary Key
    UserRoleId INT IDENTITY(1,1) PRIMARY KEY,

    -- User Information
    UserId NVARCHAR(50) NOT NULL UNIQUE,           -- User identifier (e.g., 'emp_123', 'manager_456')
    EmployeeId NVARCHAR(50) NULL,                  -- Optional FK to Employees table

    -- Role Assignment
    Role NVARCHAR(20) NOT NULL
        CHECK (Role IN ('ADMIN', 'HR_MANAGER', 'HR_STAFF', 'VIEWER')),

    -- Department (for HR_MANAGER role scoping)
    Department NVARCHAR(100) NULL,                 -- Department for HR_MANAGER data scoping

    -- Metadata
    AssignedBy NVARCHAR(50) NULL,                  -- Who assigned this role
    AssignedDate DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
    LastModified DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
    IsActive BIT NOT NULL DEFAULT 1,               -- Soft delete flag

    -- Audit Trail
    CreatedAt DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
    CreatedBy NVARCHAR(50) NULL DEFAULT SYSTEM_USER,

    -- Constraints
    CONSTRAINT CK_UserRoles_DepartmentRequired
        CHECK (
            -- HR_MANAGER must have a department
            (Role = 'HR_MANAGER' AND Department IS NOT NULL) OR
            (Role != 'HR_MANAGER')
        )
);
GO

-- Create indexes for performance
CREATE NONCLUSTERED INDEX IX_UserRoles_UserId
    ON dbo.UserRoles(UserId)
    WHERE IsActive = 1;
GO

CREATE NONCLUSTERED INDEX IX_UserRoles_Role
    ON dbo.UserRoles(Role)
    WHERE IsActive = 1;
GO

CREATE NONCLUSTERED INDEX IX_UserRoles_Department
    ON dbo.UserRoles(Department)
    WHERE Department IS NOT NULL AND IsActive = 1;
GO

CREATE NONCLUSTERED INDEX IX_UserRoles_EmployeeId
    ON dbo.UserRoles(EmployeeId)
    WHERE EmployeeId IS NOT NULL AND IsActive = 1;
GO

-- Foreign key to Employees table (if exists)
IF OBJECT_ID('dbo.Employees', 'U') IS NOT NULL
BEGIN
    PRINT 'Adding foreign key constraint to Employees table...';
    ALTER TABLE dbo.UserRoles
    ADD CONSTRAINT FK_UserRoles_Employees
        FOREIGN KEY (EmployeeId) REFERENCES dbo.Employees(EmployeeId)
        ON DELETE SET NULL;  -- Keep role assignment even if employee is deleted
END
GO

-- Create trigger for LastModified timestamp
CREATE OR ALTER TRIGGER TR_UserRoles_UpdateLastModified
ON dbo.UserRoles
AFTER UPDATE
AS
BEGIN
    SET NOCOUNT ON;

    UPDATE ur
    SET LastModified = GETUTCDATE()
    FROM dbo.UserRoles ur
    INNER JOIN inserted i ON ur.UserRoleId = i.UserRoleId;
END
GO

-- Add extended properties for documentation
EXEC sys.sp_addextendedproperty
    @name = N'MS_Description',
    @value = N'Stores user role assignments for RBAC (Role-Based Access Control) system',
    @level0type = N'SCHEMA', @level0name = N'dbo',
    @level1type = N'TABLE',  @level1name = N'UserRoles';
GO

EXEC sys.sp_addextendedproperty
    @name = N'MS_Description',
    @value = N'Unique identifier for the user (used for authentication/authorization)',
    @level0type = N'SCHEMA', @level0name = N'dbo',
    @level1type = N'TABLE',  @level1name = N'UserRoles',
    @level2type = N'COLUMN', @level2name = N'UserId';
GO

EXEC sys.sp_addextendedproperty
    @name = N'MS_Description',
    @value = N'User role: ADMIN (100), HR_MANAGER (50), HR_STAFF (30), or VIEWER (10)',
    @level0type = N'SCHEMA', @level0name = N'dbo',
    @level1type = N'TABLE',  @level1name = N'UserRoles',
    @level2type = N'COLUMN', @level2name = N'Role';
GO

EXEC sys.sp_addextendedproperty
    @name = N'MS_Description',
    @value = N'Department for HR_MANAGER data scoping (required for HR_MANAGER role)',
    @level0type = N'SCHEMA', @level0name = N'dbo',
    @level1type = N'TABLE',  @level1name = N'UserRoles',
    @level2type = N'COLUMN', @level2name = N'Department';
GO

PRINT 'UserRoles table created successfully!';
PRINT 'Indexes created: IX_UserRoles_UserId, IX_UserRoles_Role, IX_UserRoles_Department, IX_UserRoles_EmployeeId';
PRINT 'Trigger created: TR_UserRoles_UpdateLastModified';
GO
