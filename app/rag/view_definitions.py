"""
View Definitions and Metadata
Defines the 9 critical database views with priorities, purposes, and usage guidelines
"""

from typing import Dict, List, Any


# View priority tiers
TIER1_PRIORITY = 5  # Must use for 90% of queries
TIER2_PRIORITY = 3  # Domain-specific
TIER3_PRIORITY = 2  # Specialized


# Critical view definitions
VIEW_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    # ==================== TIER 1: ALWAYS USE FIRST ====================

    "vw_EmployeeMaster_Vms": {
        "tier": 1,
        "priority": TIER1_PRIORITY,
        "rating": "[STAR][STAR][STAR][STAR][STAR]",
        "purpose": "Complete employee master record with ALL organizational hierarchy pre-joined (18 tables)",

        "pre_joins": [
            "EmployeeMaster", "SectionMaster", "DeptMaster", "BranchMaster",
            "CompanyMaster", "CategoryMaster", "DesignationMaster", "GradeMaster",
            "BiometricMaster", "ContractorMaster", "AttendanceMaster", "ShiftMaster"
        ],

        "key_columns": {
            "employee_identity": ["Ecode", "CorpEmpCode", "EmpName", "Active"],
            "organizational_hierarchy": ["Dname", "SecName", "BranchName", "CName"],
            "employee_metadata": ["DateofJoin", "PresentCardNo", "Sex", "DateofBirth"],
            "biometric": ["FP1_ID", "FP2_ID", "IsEnrolled"],
            "contractor": ["ContractorID"]
        },

        "always_use_for": [
            "ANY employee query with department/section/branch",
            "Employee count by department/section/branch",
            "Employee organizational hierarchy queries",
            "Employee personal details",
            "Active vs inactive employees",
            "Employee filtering by name, code, date of joining"
        ],

        "critical_filters": [
            "WHERE Active = 1  -- ALWAYS filter for active employees unless specifically asking for inactive",
            "WHERE Dname LIKE '%IT%'  -- Department name filter",
            "WHERE EmpName LIKE '%John%'  -- Employee name search"
        ],

        "sample_queries": [
            {
                "question": "How many employees in each department?",
                "sql": "SELECT Dname, COUNT(*) AS EmployeeCount FROM dbo.vw_EmployeeMaster_Vms WHERE Active = 1 GROUP BY Dname ORDER BY EmployeeCount DESC"
            },
            {
                "question": "Show me employees in IT department",
                "sql": "SELECT Ecode, CorpEmpCode, EmpName, Dname, SecName FROM dbo.vw_EmployeeMaster_Vms WHERE Active = 1 AND Dname LIKE '%IT%'"
            },
            {
                "question": "How many total active employees?",
                "sql": "SELECT COUNT(*) AS TotalEmployees FROM dbo.vw_EmployeeMaster_Vms WHERE Active = 1"
            }
        ],

        "do_not_use": [
            "DO NOT manually JOIN EmployeeMaster + SectionMaster + DeptMaster",
            "DO NOT manually JOIN EmployeeMaster + BranchMaster + CompanyMaster",
            "USE THIS VIEW INSTEAD - it has all JOINs pre-built!"
        ]
    },

    "vw_RawPunchDetail": {
        "tier": 1,
        "priority": TIER1_PRIORITY,
        "rating": "[STAR][STAR][STAR][STAR][STAR]",
        "purpose": "Attendance/punch records with employee details, machine info, and organizational context pre-joined",

        "pre_joins": [
            "MachineRawPunch", "EmployeeMaster", "MachineMaster", "DeptMaster",
            "SectionMaster", "BranchMaster", "CompanyMaster"
        ],

        "key_columns": {
            "punch_data": ["ATDate", "ATTime", "InTime", "OutTime", "WorkHour"],
            "employee": ["ECode", "EmpName", "CorpEmpCode"],
            "machine": ["MachineID", "MachineName", "IPAddress", "Location"],
            "organizational": ["Dname", "SecName", "BranchName"]
        },

        "always_use_for": [
            "ANY attendance or punch query",
            "Time tracking queries",
            "Employee in/out times",
            "Attendance by date/date range",
            "Punch logs by employee/machine/department",
            "Work hour calculations"
        ],

        "critical_filters": [
            "WHERE ATDate = '2025-01-20'  -- Specific date",
            "WHERE ATDate BETWEEN '2025-01-01' AND '2025-01-31'  -- Date range",
            "WHERE ECode = 12345  -- Specific employee",
            "WHERE Dname LIKE '%IT%'  -- Department filter"
        ],

        "sample_queries": [
            {
                "question": "Show attendance for today",
                "sql": "SELECT EmpName, ATDate, InTime, OutTime, WorkHour FROM dbo.vw_RawPunchDetail WHERE ATDate = CAST(GETDATE() AS DATE)"
            },
            {
                "question": "Which employees punched in late today?",
                "sql": "SELECT EmpName, InTime FROM dbo.vw_RawPunchDetail WHERE ATDate = CAST(GETDATE() AS DATE) AND InTime > '09:30:00'"
            }
        ],

        "do_not_use": [
            "DO NOT manually JOIN MachineRawPunch + EmployeeMaster + MachineMaster",
            "USE THIS VIEW INSTEAD - it has all attendance context!"
        ]
    },

    "AllEmployeeUnion": {
        "tier": 1,
        "priority": TIER1_PRIORITY,
        "rating": "[STAR][STAR][STAR][STAR][STAR]",
        "purpose": "Union of EmployeeMaster + EmployeeMaster_Deleted (includes both active and deleted employees)",

        "pre_joins": [
            "EmployeeMaster UNION ALL EmployeeMaster_Deleted"
        ],

        "key_columns": {
            "employee": ["Ecode", "CorpEmpCode", "EmpName", "Active"],
            "metadata": ["DateofJoin", "LeavingDate", "LeavingReason"]
        },

        "always_use_for": [
            "Total employee count (active + deleted)",
            "Historical employee queries",
            "Queries that need to include deleted/inactive employees",
            "Employee count over time"
        ],

        "critical_filters": [
            "WHERE Active = 1  -- Only active employees",
            "WHERE Active = 0  -- Only deleted/inactive employees",
            "-- No WHERE clause = all employees (active + deleted)"
        ],

        "sample_queries": [
            {
                "question": "How many total employees (including deleted)?",
                "sql": "SELECT COUNT(*) AS TotalEmployees FROM dbo.AllEmployeeUnion"
            },
            {
                "question": "How many active employees?",
                "sql": "SELECT COUNT(*) AS ActiveEmployees FROM dbo.AllEmployeeUnion WHERE Active = 1"
            }
        ],

        "do_not_use": [
            "DO NOT query EmployeeMaster alone if you need total count",
            "DO NOT manually UNION EmployeeMaster and EmployeeMaster_Deleted",
            "USE THIS VIEW INSTEAD!"
        ]
    },

    # ==================== TIER 2: DOMAIN-SPECIFIC ====================

    "View_Visitor_EnrollmentDetail": {
        "tier": 2,
        "priority": TIER2_PRIORITY,
        "rating": "[STAR][STAR][STAR][STAR]",
        "purpose": "Visitor enrollment details with host employee and access information",

        "always_use_for": [
            "Visitor queries",
            "Visitor enrollment status",
            "Visitor access logs",
            "Host employee for visitors"
        ],

        "sample_queries": [
            {
                "question": "Show all visitors enrolled today",
                "sql": "SELECT * FROM dbo.View_Visitor_EnrollmentDetail WHERE EnrollmentDate = CAST(GETDATE() AS DATE)"
            }
        ]
    },

    "View_Contractor_Detail": {
        "tier": 2,
        "priority": TIER2_PRIORITY,
        "rating": "[STAR][STAR][STAR][STAR]",
        "purpose": "Contractor details with company and employee linkage",

        "always_use_for": [
            "Contractor queries",
            "Contractor company information",
            "Contractor employee relationships"
        ],

        "sample_queries": [
            {
                "question": "Show all active contractors",
                "sql": "SELECT * FROM dbo.View_Contractor_Detail WHERE Active = 1"
            }
        ]
    },

    "View_Employee_Terminal_Authentication_Relation": {
        "tier": 2,
        "priority": TIER2_PRIORITY,
        "rating": "[STAR][STAR][STAR][STAR]",
        "purpose": "Employee access control permissions to terminals/devices",

        "always_use_for": [
            "Access control queries",
            "Employee terminal permissions",
            "Which employees can access which terminals",
            "Terminal access authorization"
        ],

        "sample_queries": [
            {
                "question": "Which employees have access to terminal 101?",
                "sql": "SELECT * FROM dbo.View_Employee_Terminal_Authentication_Relation WHERE TerminalID = 101"
            }
        ]
    },

    "View_EmployeeByUserGroupPolicy": {
        "tier": 2,
        "priority": TIER2_PRIORITY,
        "rating": "[STAR][STAR][STAR][STAR]",
        "purpose": "Employee grouping by user group policies",

        "always_use_for": [
            "User group queries",
            "Policy-based employee grouping",
            "Employee access policies"
        ],

        "sample_queries": [
            {
                "question": "Show employees in Admin group",
                "sql": "SELECT * FROM dbo.View_EmployeeByUserGroupPolicy WHERE GroupName = 'Admin'"
            }
        ]
    },

    # ==================== TIER 3: SPECIALIZED ====================

    "Vw_TerminalDetail_VMS": {
        "tier": 3,
        "priority": TIER3_PRIORITY,
        "rating": "[STAR][STAR][STAR]",
        "purpose": "Terminal/device configuration and status details",

        "always_use_for": [
            "Terminal/device configuration queries",
            "Device status (online/offline)",
            "Terminal location and settings"
        ],

        "sample_queries": [
            {
                "question": "Show all online terminals",
                "sql": "SELECT * FROM dbo.Vw_TerminalDetail_VMS WHERE Status = 'Online'"
            }
        ]
    },

    "vw_VisitorBasicDetail": {
        "tier": 3,
        "priority": TIER3_PRIORITY,
        "rating": "[STAR][STAR][STAR]",
        "purpose": "Basic visitor information lookup (simplified version)",

        "always_use_for": [
            "Simple visitor lookup",
            "Basic visitor details"
        ],

        "sample_queries": [
            {
                "question": "Find visitor by name",
                "sql": "SELECT * FROM dbo.vw_VisitorBasicDetail WHERE VisitorName LIKE '%John%'"
            }
        ]
    }
}


# Deprecated tables that should NOT be used
DEPRECATED_TABLES = {
    "EmpDepartRole": {
        "reason": "EMPTY TABLE (0 rows) - Use EmployeeMaster.SecCode -> SectionMaster.Dcode -> DeptMaster instead",
        "replacement": "vw_EmployeeMaster_Vms (has Dname column)"
    }
}


def get_view_by_tier(tier: int) -> Dict[str, Dict[str, Any]]:
    """Get all views for a specific tier"""
    return {
        name: details
        for name, details in VIEW_DEFINITIONS.items()
        if details["tier"] == tier
    }


def get_all_view_names() -> List[str]:
    """Get list of all view names"""
    return list(VIEW_DEFINITIONS.keys())


def get_view_priority(view_name: str) -> int:
    """Get priority for a specific view"""
    return VIEW_DEFINITIONS.get(view_name, {}).get("priority", 0)
