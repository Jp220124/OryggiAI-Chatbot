# Database Setup for Phase 2 RBAC

## Overview

This directory contains SQL scripts for setting up the UserRoles table required for Role-Based Access Control (RBAC) in Phase 2.

## Directory Structure

```
database/
├── schema/
│   └── create_user_roles.sql    # Table schema with indexes and constraints
├── seed/
│   └── seed_user_roles.sql      # Test data for all 4 roles
└── README.md                     # This file
```

## Quick Start

### 1. Create the UserRoles Table

Run the schema creation script in SQL Server Management Studio (SSMS) or using sqlcmd:

```sql
-- In SSMS:
-- 1. Open database/schema/create_user_roles.sql
-- 2. Ensure you're connected to Oryggi_HR_DB
-- 3. Execute the script (F5)
```

Or via command line:
```bash
sqlcmd -S YOUR_SERVER_NAME -d Oryggi_HR_DB -i database/schema/create_user_roles.sql
```

### 2. Seed Test Data

After creating the table, populate it with test users:

```sql
-- In SSMS:
-- 1. Open database/seed/seed_user_roles.sql
-- 2. Execute the script (F5)
```

Or via command line:
```bash
sqlcmd -S YOUR_SERVER_NAME -d Oryggi_HR_DB -i database/seed/seed_user_roles.sql
```

## Schema Details

### UserRoles Table

| Column | Type | Description |
|--------|------|-------------|
| UserRoleId | INT IDENTITY | Primary key |
| UserId | NVARCHAR(50) | **Unique** user identifier (e.g., 'emp_123') |
| EmployeeId | NVARCHAR(50) | Optional FK to Employees table |
| Role | NVARCHAR(20) | Role: ADMIN, HR_MANAGER, HR_STAFF, or VIEWER |
| Department | NVARCHAR(100) | **Required for HR_MANAGER** (for data scoping) |
| AssignedBy | NVARCHAR(50) | Who assigned this role |
| AssignedDate | DATETIME2 | When role was assigned |
| LastModified | DATETIME2 | Auto-updated on changes |
| IsActive | BIT | Soft delete flag |

### Indexes

- `IX_UserRoles_UserId` - Fast user lookup
- `IX_UserRoles_Role` - Role-based queries
- `IX_UserRoles_Department` - Department filtering
- `IX_UserRoles_EmployeeId` - Employee relationship

### Constraints

- **Unique constraint** on UserId
- **Check constraint** ensuring HR_MANAGER has Department
- **Foreign key** to Employees table (if exists)
- **Trigger** for auto-updating LastModified timestamp

## Test Data

The seed script creates **19 test users**:

### ADMIN (Level 100) - 2 users
- `admin_001` - System administrator
- `admin_002` - Secondary admin

Full system access, no data scoping.

### HR_MANAGER (Level 50) - 5 users
- `manager_001` - IT Department
- `manager_002` - Finance Department
- `manager_003` - Sales Department
- `manager_004` - HR Department
- `manager_005` - Operations Department

Department-level access with data scoping.

### HR_STAFF (Level 30) - 7 users
- `staff_001` - IT
- `staff_002` - Finance
- `staff_003` - Sales
- `staff_004` - HR
- `staff_005` - Operations
- `staff_006` - IT
- `staff_007` - Finance

Team-level access, sees own data.

### VIEWER (Level 10) - 5 users
- `viewer_001` through `viewer_005`

Read-only access, sees only own data.

## Role Hierarchy & Data Scoping

```
ADMIN (100)
  └─ Full access to all data

HR_MANAGER (50)
  └─ Access to all employees in their department
     Example: manager_001 sees all IT employees

HR_STAFF (30)
  └─ Access to own data only
     Example: staff_001 sees only their own employee record

VIEWER (10)
  └─ Read-only access to own data only
```

## Verification Queries

### Check all users by role:

```sql
SELECT
    Role,
    COUNT(*) AS UserCount
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
```

### Check department distribution:

```sql
SELECT
    ISNULL(Department, 'N/A') AS Department,
    COUNT(*) AS UserCount
FROM dbo.UserRoles
WHERE IsActive = 1
GROUP BY Department
ORDER BY Department;
```

### Get user's role:

```sql
SELECT
    UserId,
    Role,
    Department,
    AssignedBy,
    AssignedDate
FROM dbo.UserRoles
WHERE UserId = 'manager_001'
  AND IsActive = 1;
```

## Integration with RBAC Middleware

The `RBACMiddleware` class (`app/middleware/rbac.py`) uses this table to:

1. **Get user role**: `get_user_role(user_id)` queries UserRoles
2. **Check permissions**: `check_permission(user_role, tool_name)` validates access
3. **Apply data scoping**: `apply_data_scoping(sql, user_role, department)` filters queries

Example:

```python
from app.middleware.rbac import rbac_middleware

# Get user's role from database
role = rbac_middleware.get_user_role("manager_001")
# Returns: "HR_MANAGER"

# Apply data scoping to SQL query
sql = "SELECT * FROM Employees"
scoped_sql = rbac_middleware.apply_data_scoping(
    sql_query=sql,
    user_role=role,
    department="IT"
)
# Returns: "SELECT * FROM Employees WHERE Department = 'IT'"
```

## Troubleshooting

### Table already exists error

If you need to recreate the table:

```sql
-- The create script automatically handles this
-- Just re-run: database/schema/create_user_roles.sql
```

### Foreign key constraint error

If Employees table doesn't exist, the FK creation is skipped automatically. No action needed.

### Seed data already exists

The seed script deletes existing test users before inserting. Safe to re-run anytime.

## Next Steps

After setting up the database:

1. Verify test users were created correctly
2. Test RBAC middleware with different roles
3. Implement QueryDatabaseTool (Phase 2 Day 4)
4. Run integration tests

## Related Documentation

- `app/middleware/rbac.py` - RBAC middleware implementation
- `app/middleware/audit_logger.py` - Security audit logging
- `tests/test_rbac.py` - Unit tests for RBAC
- `PHASE2_PLAN.md` - Complete Phase 2 implementation plan
