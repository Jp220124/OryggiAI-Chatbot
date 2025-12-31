# Phase 2: Tool Registry + RBAC Implementation Plan

## Executive Summary

**Phase:** 2 of 6
**Duration:** Week 3 (5-7 days)
**Goal:** Multi-role permission system with extensible tool registry
**Dependencies:** Phase 1 (RAG-Enhanced SQL) - ✅ COMPLETE

**Deliverables:**
1. Tool Registry framework for extensible chatbot capabilities
2. Role-Based Access Control (RBAC) middleware
3. Multi-role user permission system (ADMIN, HR_MANAGER, HR_STAFF, VIEWER)
4. QueryDatabaseTool with role-scoped data access
5. UserRoles database table
6. Comprehensive RBAC testing suite

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Tool Registry Design](#tool-registry-design)
3. [RBAC System Design](#rbac-system-design)
4. [Database Schema](#database-schema)
5. [Implementation Steps](#implementation-steps)
6. [Code Examples](#code-examples)
7. [Testing Strategy](#testing-strategy)
8. [Success Criteria](#success-criteria)

---

## Architecture Overview

### System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  FastAPI Endpoints                           │
│              /api/chat/query (existing)                      │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│              RBAC Middleware (NEW)                           │
│        • Extract user role from JWT token                    │
│        • Check tool permissions                              │
│        • Apply data scoping rules                            │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│              Tool Registry (NEW)                             │
│        • QueryDatabaseTool                                   │
│        • (Future: ReportTools, ActionTools)                  │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│         RAG SQL Agent (Phase 1 - existing)                   │
│        • Few-shot retrieval                                  │
│        • Schema retrieval                                    │
│        • SQL generation                                      │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│              SQL Server Database                             │
│        • EmployeeMaster, DeptMaster, etc.                    │
│        • UserRoles (NEW)                                     │
└─────────────────────────────────────────────────────────────┘
```

### Request Flow with RBAC

```
1. User Request
   ↓
2. JWT Token Validation → Extract user_id
   ↓
3. Query UserRoles Table → Get role (ADMIN, HR_MANAGER, etc.)
   ↓
4. RBAC Permission Check → Can user use QueryDatabaseTool?
   ↓
5. Apply Data Scoping → Based on role, filter data
   ↓
6. Execute Tool → RAG SQL Agent generates and runs query
   ↓
7. Return Scoped Results → Only data user is allowed to see
```

---

## Tool Registry Design

### Base Tool Class

**Purpose:** Define standard interface for all chatbot tools

**File:** `app/tools/base_tool.py`

**Key Features:**
- Tool metadata (name, description)
- RBAC requirements
- Permission checking
- Execution interface
- Error handling

**Design Principles:**
1. **Extensibility:** Easy to add new tools
2. **Security:** Permission checks built-in
3. **Consistency:** All tools follow same pattern
4. **Testability:** Mock-friendly interface

### Tool Registry

**Purpose:** Central registry of all available tools

**File:** `app/tools/__init__.py`

**Capabilities:**
- Tool discovery
- Tool validation
- Tool execution
- Permission enforcement

---

## RBAC System Design

### Role Hierarchy

```
ADMIN (Level 100)
  ├─ Full database access
  ├─ Can query all tables
  ├─ Can execute all tools
  └─ Can perform destructive actions

HR_MANAGER (Level 50)
  ├─ HR department data access
  ├─ Can query HR-related tables
  ├─ Can generate reports
  └─ Cannot execute actions

HR_STAFF (Level 30)
  ├─ Own department data access
  ├─ Can query their department only
  ├─ Read-only access
  └─ Cannot generate reports

VIEWER (Level 10)
  ├─ Self data access only
  ├─ Can query own records
  ├─ No export capabilities
  └─ Minimal permissions
```

### Permission Model

**Tool Permissions:**
```python
TOOL_PERMISSIONS = {
    "query_database": {
        "ADMIN": {
            "allowed": True,
            "scope": "all",
            "tables": ["*"]
        },
        "HR_MANAGER": {
            "allowed": True,
            "scope": "hr_only",
            "tables": ["EmployeeMaster", "DeptMaster", "AttendanceMaster"]
        },
        "HR_STAFF": {
            "allowed": True,
            "scope": "department",
            "tables": ["EmployeeMaster", "DeptMaster"]
        },
        "VIEWER": {
            "allowed": True,
            "scope": "self",
            "tables": ["EmployeeMaster"]
        }
    }
}
```

**Data Scoping Rules:**
- **ADMIN:** No filters applied, sees all data
- **HR_MANAGER:** WHERE DeptCode IN (HR departments)
- **HR_STAFF:** WHERE DeptCode = user's department
- **VIEWER:** WHERE EmployeeCode = user's employee code

### Security Features

1. **Default Deny:** No permission unless explicitly granted
2. **Least Privilege:** Users get minimum necessary access
3. **Audit Logging:** All permission checks logged
4. **SQL Injection Prevention:** Existing query validator kept
5. **Parameter Validation:** All user inputs validated

---

## Database Schema

### UserRoles Table

**Purpose:** Map users to their roles and scoping information

```sql
CREATE TABLE UserRoles (
    user_id VARCHAR(50) PRIMARY KEY,
    role VARCHAR(20) NOT NULL CHECK (role IN ('ADMIN', 'HR_MANAGER', 'HR_STAFF', 'VIEWER')),
    employee_code VARCHAR(10),  -- For VIEWER scope
    department_code INT,         -- For HR_STAFF scope
    department_ids VARCHAR(MAX), -- Comma-separated for HR_MANAGER
    created_at DATETIME DEFAULT GETDATE(),
    updated_at DATETIME DEFAULT GETDATE(),
    is_active BIT DEFAULT 1,

    -- Foreign keys
    CONSTRAINT FK_UserRoles_Employee FOREIGN KEY (employee_code)
        REFERENCES EmployeeMaster(EmployeeCode),
    CONSTRAINT FK_UserRoles_Department FOREIGN KEY (department_code)
        REFERENCES DeptMaster(Dcode)
);

-- Indexes for performance
CREATE INDEX idx_user_role ON UserRoles(role);
CREATE INDEX idx_user_active ON UserRoles(is_active);
CREATE INDEX idx_user_dept ON UserRoles(department_code);
```

### Seed Data

```sql
-- Admin user (full access)
INSERT INTO UserRoles (user_id, role, employee_code, department_code, is_active)
VALUES ('admin_user', 'ADMIN', NULL, NULL, 1);

-- HR Manager (HR departments only)
INSERT INTO UserRoles (user_id, role, employee_code, department_code, department_ids, is_active)
VALUES ('hr_manager', 'HR_MANAGER', 'EMP001', 1, '1,2,3', 1);

-- HR Staff (single department)
INSERT INTO UserRoles (user_id, role, employee_code, department_code, is_active)
VALUES ('hr_staff', 'HR_STAFF', 'EMP002', 1, 1);

-- Viewer (self only)
INSERT INTO UserRoles (user_id, role, employee_code, department_code, is_active)
VALUES ('viewer_user', 'VIEWER', 'EMP003', NULL, 1);
```

---

## Implementation Steps

### Day 1: Setup & Base Tool Class

**Tasks:**
1. Create `app/tools/` directory structure
2. Implement `ChatbotTool` base class
3. Create tool registry
4. Write unit tests for base class

**Files to Create:**
- `app/tools/__init__.py`
- `app/tools/base_tool.py`
- `tests/test_base_tool.py`

**Validation:**
- [ ] Base class can be instantiated
- [ ] Permission checking works
- [ ] Error handling works
- [ ] All tests pass

---

### Day 2: RBAC Middleware

**Tasks:**
1. Create `app/middleware/` directory
2. Implement role hierarchy
3. Implement permission checking
4. Integrate with JWT authentication
5. Write RBAC tests

**Files to Create:**
- `app/middleware/__init__.py`
- `app/middleware/rbac.py`
- `app/middleware/audit_logger.py`
- `tests/test_rbac.py`

**Validation:**
- [ ] Role hierarchy enforced
- [ ] Permission checks working
- [ ] Audit logs created
- [ ] All tests pass

---

### Day 3: Database Schema & UserRoles

**Tasks:**
1. Create UserRoles table
2. Add foreign key constraints
3. Create indexes
4. Seed test data
5. Create ORM models (if using)

**Files to Create:**
- `database/migrations/002_create_user_roles.sql`
- `app/models/user_roles.py` (optional)
- `tests/test_user_roles_db.py`

**Validation:**
- [ ] Table created successfully
- [ ] Constraints working
- [ ] Seed data inserted
- [ ] Query performance acceptable

---

### Day 4: QueryDatabaseTool Implementation

**Tasks:**
1. Implement QueryDatabaseTool class
2. Integrate with RAG SQL Agent (Phase 1)
3. Apply data scoping filters
4. Add permission checks
5. Write integration tests

**Files to Create:**
- `app/tools/database_tools.py`
- `tests/test_query_database_tool.py`

**Validation:**
- [ ] Tool executes queries correctly
- [ ] Role-based scoping works
- [ ] Permission checks enforced
- [ ] All roles tested

---

### Day 5: Integration & Testing

**Tasks:**
1. Integrate tools with FastAPI endpoints
2. Update chat endpoint to use RBAC
3. End-to-end testing
4. Performance testing
5. Security testing

**Files to Modify:**
- `app/api/routes.py`
- `app/main.py`
- `tests/test_integration.py`

**Validation:**
- [ ] ADMIN can query all data
- [ ] HR_MANAGER sees HR data only
- [ ] HR_STAFF sees department data only
- [ ] VIEWER sees own data only
- [ ] Unauthorized access blocked
- [ ] All audit logs working

---

## Code Examples

### 1. Base Tool Class

```python
# app/tools/base_tool.py

from typing import Any, Dict, List, Optional
from abc import ABC, abstractmethod
from loguru import logger

class ChatbotTool(ABC):
    """
    Base class for all chatbot tools
    Provides standardized interface and RBAC integration
    """

    # Tool metadata
    name: str
    description: str
    rbac_required: List[str]  # Roles that can use this tool
    destructive: bool = False  # Requires confirmation?

    def __init__(self):
        """Initialize tool"""
        if not hasattr(self, 'name'):
            raise ValueError("Tool must define 'name' attribute")
        if not hasattr(self, 'description'):
            raise ValueError("Tool must define 'description' attribute")
        if not hasattr(self, 'rbac_required'):
            raise ValueError("Tool must define 'rbac_required' attribute")

    def check_permission(self, user_role: str) -> tuple[bool, Optional[str]]:
        """
        Check if user role has permission to use this tool

        Args:
            user_role: User's role (ADMIN, HR_MANAGER, etc.)

        Returns:
            (allowed: bool, error_message: Optional[str])
        """
        if user_role in self.rbac_required:
            logger.info(f"Permission granted: {user_role} can use {self.name}")
            return True, None
        else:
            error = f"Permission denied: {user_role} cannot use {self.name}"
            logger.warning(error)
            return False, error

    @abstractmethod
    def _run(self, **kwargs) -> Any:
        """
        Execute the tool
        Must be implemented by subclasses
        """
        pass

    def run(self, user_role: str, **kwargs) -> Dict[str, Any]:
        """
        Execute tool with permission checking

        Args:
            user_role: User's role
            **kwargs: Tool-specific parameters

        Returns:
            {
                "success": bool,
                "result": Any,
                "error": Optional[str]
            }
        """
        # Check permission
        allowed, error = self.check_permission(user_role)
        if not allowed:
            return {
                "success": False,
                "result": None,
                "error": error
            }

        # Execute tool
        try:
            result = self._run(**kwargs)
            return {
                "success": True,
                "result": result,
                "error": None
            }
        except Exception as e:
            logger.error(f"Tool execution failed: {str(e)}")
            return {
                "success": False,
                "result": None,
                "error": str(e)
            }
```

---

### 2. RBAC Middleware

```python
# app/middleware/rbac.py

from typing import Dict, Optional, Tuple, List
from loguru import logger

# Role hierarchy (higher number = more permissions)
ROLE_HIERARCHY = {
    "ADMIN": 100,
    "HR_MANAGER": 50,
    "HR_STAFF": 30,
    "VIEWER": 10
}

# Tool permissions configuration
TOOL_PERMISSIONS = {
    "query_database": {
        "ADMIN": {
            "allowed": True,
            "scope": "all",
            "tables": ["*"],
            "filters": []
        },
        "HR_MANAGER": {
            "allowed": True,
            "scope": "hr_only",
            "tables": ["EmployeeMaster", "DeptMaster", "AttendanceMaster"],
            "filters": ["WHERE DeptCode IN (user_departments)"]
        },
        "HR_STAFF": {
            "allowed": True,
            "scope": "department",
            "tables": ["EmployeeMaster", "DeptMaster"],
            "filters": ["WHERE DeptCode = user_department"]
        },
        "VIEWER": {
            "allowed": True,
            "scope": "self",
            "tables": ["EmployeeMaster"],
            "filters": ["WHERE EmployeeCode = user_employee_code"]
        }
    }
}

class RBACMiddleware:
    """Role-Based Access Control middleware"""

    def __init__(self, db_manager):
        """Initialize with database connection"""
        self.db = db_manager

    def get_user_role(self, user_id: str) -> Optional[Dict]:
        """
        Get user's role and scoping information

        Args:
            user_id: User identifier

        Returns:
            {
                "role": str,
                "employee_code": str,
                "department_code": int,
                "department_ids": List[int]
            }
        """
        query = """
        SELECT
            role,
            employee_code,
            department_code,
            department_ids
        FROM UserRoles
        WHERE user_id = ? AND is_active = 1
        """

        result = self.db.execute_query(query, (user_id,))

        if not result or len(result) == 0:
            logger.warning(f"No role found for user: {user_id}")
            return None

        user_data = result[0]

        # Parse department_ids (comma-separated string to list)
        dept_ids = []
        if user_data.get("department_ids"):
            dept_ids = [int(d) for d in user_data["department_ids"].split(",")]

        return {
            "role": user_data["role"],
            "employee_code": user_data.get("employee_code"),
            "department_code": user_data.get("department_code"),
            "department_ids": dept_ids
        }

    def check_tool_permission(
        self,
        user_role: str,
        tool_name: str
    ) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """
        Check if user role can use the specified tool

        Args:
            user_role: User's role
            tool_name: Name of tool to check

        Returns:
            (
                allowed: bool,
                error_message: Optional[str],
                permission_config: Optional[Dict]
            )
        """
        # Check if tool exists
        if tool_name not in TOOL_PERMISSIONS:
            return False, f"Unknown tool: {tool_name}", None

        # Check if role has permission
        tool_config = TOOL_PERMISSIONS[tool_name]
        if user_role not in tool_config:
            return False, f"Role {user_role} cannot use {tool_name}", None

        permission_config = tool_config[user_role]

        if not permission_config.get("allowed", False):
            return False, f"Tool {tool_name} not allowed for {user_role}", None

        logger.info(f"Permission check passed: {user_role} → {tool_name}")
        return True, None, permission_config

    def apply_data_scoping(
        self,
        sql_query: str,
        user_role_data: Dict,
        permission_config: Dict
    ) -> str:
        """
        Apply role-based data scoping to SQL query

        Args:
            sql_query: Original SQL query
            user_role_data: User's role and scoping info
            permission_config: Permission configuration for tool

        Returns:
            Modified SQL query with filters applied
        """
        scope = permission_config.get("scope")

        if scope == "all":
            # ADMIN - no filtering
            return sql_query

        elif scope == "hr_only":
            # HR_MANAGER - filter by department IDs
            dept_ids = user_role_data.get("department_ids", [])
            if dept_ids:
                dept_list = ",".join(str(d) for d in dept_ids)
                filter_clause = f"AND e.DeptCode IN ({dept_list})"
                sql_query = self._inject_where_clause(sql_query, filter_clause)

        elif scope == "department":
            # HR_STAFF - filter by single department
            dept_code = user_role_data.get("department_code")
            if dept_code:
                filter_clause = f"AND e.DeptCode = {dept_code}"
                sql_query = self._inject_where_clause(sql_query, filter_clause)

        elif scope == "self":
            # VIEWER - filter by employee code
            emp_code = user_role_data.get("employee_code")
            if emp_code:
                filter_clause = f"AND e.EmployeeCode = '{emp_code}'"
                sql_query = self._inject_where_clause(sql_query, filter_clause)

        logger.info(f"Applied data scoping: {scope}")
        return sql_query

    def _inject_where_clause(self, sql_query: str, filter_clause: str) -> str:
        """
        Safely inject WHERE clause into SQL query

        Args:
            sql_query: Original query
            filter_clause: Filter to add

        Returns:
            Modified query
        """
        # Simple implementation - can be enhanced with SQL parsing
        if "WHERE" in sql_query.upper():
            # Already has WHERE clause, append with AND
            sql_query = sql_query.strip()
            if not sql_query.endswith(";"):
                sql_query += " " + filter_clause
            else:
                sql_query = sql_query[:-1] + " " + filter_clause + ";"
        else:
            # No WHERE clause, add one
            # Find position before ORDER BY, GROUP BY, or end
            insert_pos = len(sql_query)
            for keyword in [" ORDER BY ", " GROUP BY ", " LIMIT ", ";"]:
                pos = sql_query.upper().find(keyword)
                if pos != -1:
                    insert_pos = min(insert_pos, pos)

            filter_with_where = filter_clause.replace("AND", "WHERE", 1)
            sql_query = sql_query[:insert_pos] + " " + filter_with_where + sql_query[insert_pos:]

        return sql_query

# Global RBAC instance (initialized with db_manager)
rbac_middleware = None

def initialize_rbac(db_manager):
    """Initialize RBAC middleware with database connection"""
    global rbac_middleware
    rbac_middleware = RBACMiddleware(db_manager)
    logger.info("RBAC middleware initialized")
```

---

### 3. QueryDatabaseTool

```python
# app/tools/database_tools.py

from typing import Any, Dict
from app.tools.base_tool import ChatbotTool
from app.agents.sql_agent import sql_agent
from app.middleware.rbac import rbac_middleware
from loguru import logger

class QueryDatabaseTool(ChatbotTool):
    """
    Tool for querying database with natural language
    Integrates with RAG SQL Agent from Phase 1
    Applies RBAC data scoping
    """

    name = "query_database"
    description = "Query database using natural language questions"
    rbac_required = ["ADMIN", "HR_MANAGER", "HR_STAFF", "VIEWER"]
    destructive = False

    def _run(
        self,
        question: str,
        user_id: str,
        user_role: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute database query with RBAC enforcement

        Args:
            question: Natural language question
            user_id: User identifier
            user_role: User's role

        Returns:
            {
                "sql_query": str,
                "results": List[Dict],
                "result_count": int,
                "tables_used": List[str],
                "scope_applied": str
            }
        """
        logger.info(f"QueryDatabaseTool: {question} (user: {user_id}, role: {user_role})")

        # Step 1: Get user role data
        user_role_data = rbac_middleware.get_user_role(user_id)
        if not user_role_data:
            raise ValueError(f"User {user_id} has no role assigned")

        # Step 2: Check tool permission
        allowed, error, permission_config = rbac_middleware.check_tool_permission(
            user_role,
            self.name
        )

        if not allowed:
            raise PermissionError(error)

        # Step 3: Generate SQL using RAG Agent (Phase 1)
        sql_result = sql_agent.generate_sql(
            question=question,
            tenant_id=kwargs.get("tenant_id", "default"),
            user_id=user_id
        )

        sql_query = sql_result["sql_query"]
        logger.info(f"Generated SQL: {sql_query[:100]}...")

        # Step 4: Apply data scoping based on role
        scoped_sql = rbac_middleware.apply_data_scoping(
            sql_query,
            user_role_data,
            permission_config
        )

        logger.info(f"Scoped SQL: {scoped_sql[:100]}...")

        # Step 5: Execute scoped query
        results = sql_agent.execute_query(scoped_sql)

        return {
            "sql_query": scoped_sql,
            "original_sql": sql_query,
            "results": results,
            "result_count": len(results),
            "tables_used": sql_result.get("tables_referenced", []),
            "scope_applied": permission_config["scope"],
            "role": user_role
        }

# Global tool instance
query_database_tool = QueryDatabaseTool()
```

---

### 4. Integration with FastAPI

```python
# app/api/routes.py (modified)

from fastapi import APIRouter, Depends, HTTPException
from app.security.auth import get_current_user
from app.tools.database_tools import query_database_tool
from app.middleware.audit_logger import log_query_attempt
from loguru import logger

router = APIRouter()

@router.post("/api/chat/query")
async def query_chatbot(
    request: QueryRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Chat endpoint with RBAC enforcement

    Request:
        {
            "question": "How many employees in IT?"
        }

    Response:
        {
            "answer": "There are 25 employees in IT department",
            "sql_query": "SELECT COUNT(*) FROM...",
            "results": [...],
            "metadata": {
                "role": "HR_MANAGER",
                "scope_applied": "hr_only",
                "result_count": 1
            }
        }
    """
    user_id = current_user["user_id"]
    user_role = current_user["role"]  # Extracted from JWT or UserRoles table

    logger.info(f"Query request from {user_id} ({user_role}): {request.question}")

    try:
        # Execute query through tool (RBAC enforced)
        result = query_database_tool.run(
            user_role=user_role,
            question=request.question,
            user_id=user_id
        )

        if not result["success"]:
            # Permission denied or execution error
            log_query_attempt(
                user_id=user_id,
                question=request.question,
                status="denied",
                error=result["error"]
            )
            raise HTTPException(status_code=403, detail=result["error"])

        # Format response
        query_result = result["result"]

        # Generate natural language answer
        answer = sql_agent._format_answer(
            request.question,
            query_result["results"]
        )

        # Log successful query
        log_query_attempt(
            user_id=user_id,
            question=request.question,
            status="success",
            result_count=query_result["result_count"]
        )

        return {
            "answer": answer,
            "sql_query": query_result["sql_query"],
            "results": query_result["results"],
            "metadata": {
                "role": user_role,
                "scope_applied": query_result["scope_applied"],
                "result_count": query_result["result_count"],
                "tables_used": query_result["tables_used"]
            }
        }

    except PermissionError as e:
        logger.warning(f"Permission denied for {user_id}: {str(e)}")
        raise HTTPException(status_code=403, detail=str(e))

    except Exception as e:
        logger.error(f"Query failed for {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
```

---

## Testing Strategy

### Unit Tests

**File:** `tests/test_base_tool.py`

```python
def test_base_tool_permission_check():
    """Test permission checking in base tool"""
    tool = MockTool()

    # ADMIN should have access
    allowed, error = tool.check_permission("ADMIN")
    assert allowed == True
    assert error is None

    # VIEWER should NOT have access
    allowed, error = tool.check_permission("VIEWER")
    assert allowed == False
    assert error is not None
```

**File:** `tests/test_rbac.py`

```python
def test_rbac_role_hierarchy():
    """Test role hierarchy enforcement"""
    assert ROLE_HIERARCHY["ADMIN"] > ROLE_HIERARCHY["HR_MANAGER"]
    assert ROLE_HIERARCHY["HR_MANAGER"] > ROLE_HIERARCHY["HR_STAFF"]
    assert ROLE_HIERARCHY["HR_STAFF"] > ROLE_HIERARCHY["VIEWER"]

def test_data_scoping_admin():
    """ADMIN should see all data (no filtering)"""
    rbac = RBACMiddleware(mock_db)

    sql = "SELECT * FROM EmployeeMaster e"
    user_data = {"role": "ADMIN"}
    config = TOOL_PERMISSIONS["query_database"]["ADMIN"]

    scoped_sql = rbac.apply_data_scoping(sql, user_data, config)

    # Should be unchanged
    assert scoped_sql == sql

def test_data_scoping_viewer():
    """VIEWER should only see own data"""
    rbac = RBACMiddleware(mock_db)

    sql = "SELECT * FROM EmployeeMaster e"
    user_data = {"role": "VIEWER", "employee_code": "EMP123"}
    config = TOOL_PERMISSIONS["query_database"]["VIEWER"]

    scoped_sql = rbac.apply_data_scoping(sql, user_data, config)

    # Should have WHERE clause
    assert "WHERE e.EmployeeCode = 'EMP123'" in scoped_sql
```

### Integration Tests

**File:** `tests/test_query_database_tool_integration.py`

```python
def test_admin_queries_all_data():
    """ADMIN should access all employee records"""
    result = query_database_tool.run(
        user_role="ADMIN",
        question="How many total employees?",
        user_id="admin_user"
    )

    assert result["success"] == True
    assert result["result"]["scope_applied"] == "all"
    assert result["result"]["result_count"] > 0

def test_viewer_queries_own_data_only():
    """VIEWER should only see their own records"""
    result = query_database_tool.run(
        user_role="VIEWER",
        question="What is my department?",
        user_id="viewer_user"
    )

    assert result["success"] == True
    assert result["result"]["scope_applied"] == "self"
    assert "WHERE e.EmployeeCode = 'EMP003'" in result["result"]["sql_query"]

def test_hr_staff_cannot_see_other_departments():
    """HR_STAFF should not see data from other departments"""
    result = query_database_tool.run(
        user_role="HR_STAFF",
        question="How many employees in Finance?",
        user_id="hr_staff"
    )

    # Should be scoped to HR department, so Finance data not visible
    assert result["success"] == True
    assert result["result"]["scope_applied"] == "department"
    # Result should be 0 or only HR dept employees
```

### Security Tests

**File:** `tests/test_security.py`

```python
def test_unauthorized_role_blocked():
    """Users with no role should be blocked"""
    with pytest.raises(PermissionError):
        query_database_tool.run(
            user_role="UNKNOWN_ROLE",
            question="Show me all data",
            user_id="malicious_user"
        )

def test_sql_injection_prevention():
    """Tool should prevent SQL injection attempts"""
    # Existing query validator should catch this
    with pytest.raises(ValueError):
        query_database_tool.run(
            user_role="ADMIN",
            question="'; DROP TABLE EmployeeMaster; --",
            user_id="admin_user"
        )

def test_scope_cannot_be_bypassed():
    """Viewer cannot bypass scoping with SQL tricks"""
    result = query_database_tool.run(
        user_role="VIEWER",
        question="Show all employees WHERE 1=1 OR EmployeeCode != 'EMP003'",
        user_id="viewer_user"
    )

    # Scoping should still be applied
    assert "WHERE e.EmployeeCode = 'EMP003'" in result["result"]["sql_query"]
```

---

## Success Criteria

### Functional Requirements

- [ ] All 4 roles (ADMIN, HR_MANAGER, HR_STAFF, VIEWER) working
- [ ] Data scoping correctly applied for each role
- [ ] QueryDatabaseTool integrated with Phase 1 RAG SQL Agent
- [ ] Permission checks enforced on all tool executions
- [ ] UserRoles table populated with test data

### Non-Functional Requirements

- [ ] RBAC permission check time: <100ms
- [ ] No unauthorized data access (100% security)
- [ ] Audit logs capture all permission checks
- [ ] Zero SQL injection vulnerabilities
- [ ] Code coverage: >90%

### Testing Requirements

- [ ] 20+ unit tests written and passing
- [ ] 10+ integration tests written and passing
- [ ] 5+ security tests written and passing
- [ ] All roles tested with realistic queries
- [ ] Edge cases handled (no role, inactive user, etc.)

---

## Dependencies & Prerequisites

### Phase 1 Components (Required)
- ✅ RAG SQL Agent (`app/agents/sql_agent.py`)
- ✅ FAISS Vector Store
- ✅ Few-shot examples
- ✅ Database connection (`app/database/`)

### New Dependencies (None)
All Phase 2 components use existing libraries:
- Python standard library (abc, typing)
- Existing FastAPI setup
- Existing database connection

### Database Access
- Write access to create UserRoles table
- Ability to add foreign key constraints
- Permission to create indexes

---

## Rollback Plan

If Phase 2 encounters critical issues:

1. **Database Rollback:**
   ```sql
   DROP TABLE UserRoles;
   ```

2. **Code Rollback:**
   - Remove `app/tools/` directory
   - Remove `app/middleware/` directory
   - Revert `app/api/routes.py` changes

3. **Fallback:**
   - Phase 1 functionality remains intact
   - Chatbot continues working with RAG SQL Agent
   - No RBAC enforcement (all users have same access)

---

## Next Steps After Phase 2

Once Phase 2 is complete, we can proceed to:

**Phase 3: Report Generation** (Week 4-5)
- PDF/Excel report tools
- Time range parsing
- Template engine integration

**Phase 4: Email Integration** (Week 5)
- SendEmailTool
- Report delivery via email
- Email validation & rate limiting

**Phase 5: Action Execution** (Week 6-7)
- Access control action tools (Grant/Block/Revoke)
- Human-in-the-loop confirmation
- Audit logging for actions

---

## Conclusion

Phase 2 establishes the **foundation for multi-role security** in the chatbot:

**Key Achievements:**
1. Extensible tool registry for future capabilities
2. Role-based permission system (4 roles)
3. Data scoping to ensure users only see authorized data
4. Audit logging for compliance
5. Integration with existing Phase 1 components

**Timeline:** 5-7 days
**Risk Level:** Low (no external dependencies)
**Complexity:** Medium (RBAC logic, SQL query modification)

**Ready to begin implementation?** ✅
