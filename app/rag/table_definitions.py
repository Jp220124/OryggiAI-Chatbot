"""
Table Definitions and Metadata
Defines critical base tables with rich descriptions, column documentation, and usage guidelines.

Note: For most queries, USE VIEWS FIRST (see view_definitions.py).
Base tables should only be used when:
1. The view doesn't exist for the required data
2. Write operations (INSERT/UPDATE) are needed
3. Specific lookup tables are required
"""

from typing import Dict, List, Any


# =============================================================================
# EMPLOYEE & ORGANIZATION TABLES
# =============================================================================

TABLE_DEFINITIONS: Dict[str, Dict[str, Any]] = {

    # ==================== CORE EMPLOYEE TABLES ====================

    "EmployeeMaster": {
        "category": "employee",
        "priority": 3,  # Lower than views (views=5)
        "description": "Core employee master table - contains all employee records with personal, organizational, and access control data",
        "business_context": "Central repository for all employee information. Each employee has a unique Ecode (internal ID) and CorpEmpCode (corporate employee ID displayed to users).",

        "key_columns": {
            "identity": {
                "Ecode": "Internal unique employee ID (auto-increment, primary key)",
                "CorpEmpCode": "Corporate employee code shown to users (e.g., 'EMP001')",
                "EmpName": "Full employee name",
                "FName": "First name",
                "LName": "Last name"
            },
            "organizational": {
                "Ccode": "Company code (FK to CompanyMaster)",
                "BranchCode": "Branch code (FK to BranchMaster)",
                "SecCode": "Section code (FK to SectionMaster)",
                "Dcode": "Department code - DERIVED via SecCode->SectionMaster.Dcode",
                "DesCode": "Designation code (FK to DesignationMaster)",
                "UserGroupID": "User group for access policies (FK to UserGroupMaster)"
            },
            "personal": {
                "DateofBirth": "Date of birth",
                "Sex": "Gender: 1=Male, 0=Female",
                "MaritalStatus": "Marital status code",
                "BloodGroup": "Blood group",
                "Telephone1": "Primary phone number",
                "E_mail": "Email address",
                "PermanentAddress": "Permanent address"
            },
            "employment": {
                "DateofJoin": "Date of joining (hiring date)",
                "LeavingDate": "Date of leaving (if applicable)",
                "LeavingReason": "Reason for leaving",
                "Active": "Status: 1=Active, 0=Inactive/Left"
            },
            "access_control": {
                "PresentCardNo": "Current access card number assigned",
                "FP1_ID": "Fingerprint 1 template ID",
                "FP2_ID": "Fingerprint 2 template ID",
                "DFP_ID": "Default fingerprint ID",
                "IsEnrolled": "Whether biometrics are enrolled"
            },
            "dates": {
                "Start_date": "Access validity start date",
                "Expiry_date": "Access validity expiry date"
            }
        },

        "important_filters": [
            "Active = 1 -- Always filter for active employees unless specifically asking for inactive",
            "Active = 0 -- For left/inactive employees only"
        ],

        "relationships": [
            "SecCode -> SectionMaster.SecCode (Section)",
            "DesCode -> DesignationMaster.DesCode (Designation)",
            "Ccode -> CompanyMaster.Ccode (Company)",
            "BranchCode -> BranchMaster.BranchCode (Branch)",
            "UserGroupID -> UserGroupMaster.UserGroupID (User Group)"
        ],

        "note": "PREFER vw_EmployeeMaster_Vms view which pre-joins all organizational hierarchy (18 tables)"
    },

    "EmployeeMaster_Deleted": {
        "category": "employee",
        "priority": 2,
        "description": "Archive table for deleted employees - same structure as EmployeeMaster",
        "business_context": "When employees are deleted from EmployeeMaster, their records are moved here for historical reference.",

        "key_columns": {
            "identity": {
                "Ecode": "Original employee ID",
                "CorpEmpCode": "Original corporate employee code",
                "EmpName": "Full employee name"
            }
        },

        "note": "Use AllEmployeeUnion view to query both active and deleted employees together"
    },

    # ==================== ORGANIZATIONAL HIERARCHY TABLES ====================

    "CompanyMaster": {
        "category": "organization",
        "priority": 2,
        "description": "Company/organization master table - top level of organizational hierarchy",
        "business_context": "Contains company/organization details. Most systems have one or few companies.",

        "key_columns": {
            "identity": {
                "Ccode": "Company code (primary key)",
                "CName": "Company name",
                "CShortName": "Company short name/abbreviation"
            },
            "details": {
                "Address": "Company address",
                "PhoneNo": "Company phone number",
                "EmailId": "Company email"
            }
        }
    },

    "BranchMaster": {
        "category": "organization",
        "priority": 2,
        "description": "Branch/location master table - second level of organizational hierarchy",
        "business_context": "Contains branch/office location details. A company can have multiple branches.",

        "key_columns": {
            "identity": {
                "BranchCode": "Branch code (primary key)",
                "BranchName": "Branch name",
                "Ccode": "Company code (FK to CompanyMaster)"
            },
            "details": {
                "Address": "Branch address",
                "City": "Branch city"
            }
        },

        "relationships": [
            "Ccode -> CompanyMaster.Ccode"
        ]
    },

    "DeptMaster": {
        "category": "organization",
        "priority": 2,
        "description": "Department master table - contains all departments",
        "business_context": "Departments are organizational units (IT, HR, Finance, etc.). Departments contain Sections.",

        "key_columns": {
            "identity": {
                "Dcode": "Department code (primary key)",
                "Dname": "Department name (e.g., 'IT Department', 'Human Resources')"
            }
        },

        "note": "Employees don't have direct Dcode - they have SecCode which links to SectionMaster.Dcode"
    },

    "SectionMaster": {
        "category": "organization",
        "priority": 2,
        "description": "Section master table - sub-unit of departments",
        "business_context": "Sections are sub-divisions within departments. Employees are assigned to Sections, not directly to Departments.",

        "key_columns": {
            "identity": {
                "SecCode": "Section code (primary key)",
                "SecName": "Section name",
                "Dcode": "Department code (FK to DeptMaster)"
            }
        },

        "relationships": [
            "Dcode -> DeptMaster.Dcode"
        ],

        "important_note": "Employee's department is derived via: EmployeeMaster.SecCode -> SectionMaster.Dcode -> DeptMaster.Dname"
    },

    "DesignationMaster": {
        "category": "organization",
        "priority": 2,
        "description": "Designation/job title master table",
        "business_context": "Contains job titles/designations (Manager, Developer, Analyst, etc.)",

        "key_columns": {
            "identity": {
                "DesCode": "Designation code (primary key)",
                "DesName": "Designation name (job title)"
            }
        }
    },

    "CategoryMaster": {
        "category": "organization",
        "priority": 2,
        "description": "Employee category master (permanent, contract, visitor, etc.)",
        "business_context": "Defines employee types/categories for classification and policy application.",

        "key_columns": {
            "identity": {
                "CatCode": "Category code (primary key)",
                "CatName": "Category name"
            }
        }
    },

    # ==================== ACCESS CONTROL TABLES ====================

    "MachineMaster": {
        "category": "access_control",
        "priority": 3,
        "description": "Access control terminals/devices master table",
        "business_context": "Contains all access control terminals (biometric devices, card readers) with their configuration.",

        "key_columns": {
            "identity": {
                "MachineID": "Machine/terminal ID (primary key)",
                "MachineName": "Machine name/description",
                "IPAddress": "Device IP address"
            },
            "configuration": {
                "MachineType": "Type of device (biometric, card reader, etc.)",
                "Location": "Physical location description",
                "Direction": "IN/OUT direction for entry/exit tracking"
            },
            "status": {
                "Status": "Online/Offline status",
                "IsActive": "Whether device is active"
            }
        },

        "note": "Use Vw_TerminalDetail_VMS view for enriched terminal information"
    },

    "TerminalGroupMaster": {
        "category": "access_control",
        "priority": 2,
        "description": "Groups of terminals for access policy management",
        "business_context": "Terminals can be grouped for easier access management (e.g., 'All Main Gates', 'Building A Doors').",

        "key_columns": {
            "identity": {
                "TerminalGroupID": "Terminal group ID (primary key)",
                "TerminalGroupName": "Group name"
            }
        }
    },

    "Authentication_Terminal": {
        "category": "access_control",
        "priority": 3,
        "description": "Employee-to-terminal access permissions mapping",
        "business_context": "Defines which employees have access to which terminals. Core table for access control.",

        "key_columns": {
            "mapping": {
                "Ecode": "Employee code",
                "TerminalID": "Terminal/Machine ID",
                "CardAuthentication": "Card access: 1001=Card, 0=No Card",
                "FingerprintAuthentication": "Fingerprint access: 2=Enabled, 0=Disabled",
                "FaceAuthentication": "Face access: 5=Enabled, 0=Disabled"
            },
            "schedule": {
                "Schedule_ID": "Access schedule ID",
                "TimeZone": "Time zone for access"
            }
        },

        "note": "Use View_Employee_Terminal_Authentication_Relation for enriched access information"
    },

    "UserGroupMaster": {
        "category": "access_control",
        "priority": 2,
        "description": "User group definitions for access policies",
        "business_context": "User groups define access policies applied to employees. Examples: Admin, Staff, Contractor.",

        "key_columns": {
            "identity": {
                "UserGroupID": "User group ID (primary key)",
                "UserGroupName": "Group name"
            }
        }
    },

    "CardMaster": {
        "category": "access_control",
        "priority": 2,
        "description": "Access card inventory and assignments",
        "business_context": "Contains all access cards (RFID cards, proximity cards) and their assignment status.",

        "key_columns": {
            "identity": {
                "CardID": "Card ID (primary key)",
                "CardNo": "Physical card number",
                "CardType": "Card type (permanent, temporary, visitor)"
            },
            "assignment": {
                "AssignedTo": "Employee Ecode if assigned",
                "IsAssigned": "Whether card is currently assigned",
                "IsActive": "Whether card is active"
            },
            "validity": {
                "ValidFrom": "Card validity start date",
                "ValidTo": "Card validity end date"
            }
        }
    },

    # ==================== ATTENDANCE TABLES ====================

    "MachineRawPunch": {
        "category": "attendance",
        "priority": 3,
        "description": "Raw attendance punch records from terminals",
        "business_context": "Contains raw punch-in/punch-out records from all terminals. Primary source for attendance data.",

        "key_columns": {
            "identity": {
                "Ecode": "Employee code",
                "MachineID": "Terminal/Machine ID where punch occurred"
            },
            "timing": {
                "ATDate": "Attendance date",
                "ATTime": "Punch time",
                "InTime": "Calculated in-time",
                "OutTime": "Calculated out-time",
                "WorkHour": "Calculated work hours"
            },
            "metadata": {
                "PunchType": "Type of punch (IN/OUT)",
                "AuthMode": "Authentication mode used (Card/Fingerprint/Face)"
            }
        },

        "note": "PREFER vw_RawPunchDetail view which pre-joins employee and machine details"
    },

    "AttendanceMaster": {
        "category": "attendance",
        "priority": 2,
        "description": "Processed daily attendance summary",
        "business_context": "Aggregated daily attendance records with status (Present, Absent, Late, etc.)",

        "key_columns": {
            "identity": {
                "Ecode": "Employee code",
                "ATDate": "Attendance date"
            },
            "status": {
                "Status": "Attendance status (P=Present, A=Absent, L=Late, etc.)",
                "InTime": "First punch-in time",
                "OutTime": "Last punch-out time",
                "WorkHours": "Total work hours"
            }
        }
    },

    "ShiftMaster": {
        "category": "attendance",
        "priority": 2,
        "description": "Work shift definitions",
        "business_context": "Defines work shifts with start/end times, break times, and working days.",

        "key_columns": {
            "identity": {
                "ShiftID": "Shift ID (primary key)",
                "ShiftName": "Shift name (e.g., 'Morning Shift', 'Night Shift')"
            },
            "timing": {
                "StartTime": "Shift start time",
                "EndTime": "Shift end time",
                "BreakTime": "Break duration in minutes"
            }
        }
    },

    # ==================== VISITOR TABLES ====================

    "VisitorMaster": {
        "category": "visitor",
        "priority": 3,
        "description": "Visitor registration records",
        "business_context": "Contains all visitor entries with personal details, host employee, and visit purpose.",

        "key_columns": {
            "identity": {
                "VisitorID": "Visitor ID (primary key)",
                "VisitorEcode": "Internal visitor code",
                "VisitorName": "Visitor full name"
            },
            "visit_details": {
                "WhomToVisit": "Host employee Ecode",
                "Purpose": "Purpose of visit",
                "ExpectedInTime": "Expected arrival time",
                "ExpectedOutTime": "Expected departure time"
            },
            "identification": {
                "IDProofType": "Type of ID (Aadhar, Passport, etc.)",
                "IDProofNo": "ID proof number",
                "Mobile": "Visitor mobile number"
            },
            "access": {
                "IssuedCardNo": "Temporary card number assigned",
                "TerminalGroupID": "Allowed terminal group"
            }
        },

        "note": "Use View_Visitor_EnrollmentDetail for enriched visitor information"
    },

    # ==================== CONTRACTOR TABLES ====================

    "ContractorMaster": {
        "category": "contractor",
        "priority": 2,
        "description": "Contractor company master table",
        "business_context": "Contains contractor companies that provide contract employees.",

        "key_columns": {
            "identity": {
                "ContractorID": "Contractor ID (primary key)",
                "ContractorName": "Contractor company name"
            },
            "details": {
                "ContactPerson": "Primary contact person",
                "PhoneNo": "Contact phone number",
                "Address": "Contractor address"
            }
        },

        "note": "Use View_Contractor_Detail for enriched contractor information"
    }
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_table_definition(table_name: str) -> Dict[str, Any]:
    """Get definition for a specific table"""
    return TABLE_DEFINITIONS.get(table_name, {})


def get_tables_by_category(category: str) -> Dict[str, Dict[str, Any]]:
    """Get all tables in a specific category"""
    return {
        name: defn for name, defn in TABLE_DEFINITIONS.items()
        if defn.get("category") == category
    }


def get_all_table_names() -> List[str]:
    """Get list of all defined table names"""
    return list(TABLE_DEFINITIONS.keys())


def get_table_priority(table_name: str) -> int:
    """Get priority for a specific table"""
    return TABLE_DEFINITIONS.get(table_name, {}).get("priority", 1)


def create_table_document(table_name: str) -> str:
    """
    Create rich documentation for a table

    Args:
        table_name: Name of the table

    Returns:
        Enriched text document describing the table
    """
    if table_name not in TABLE_DEFINITIONS:
        return f"TABLE: dbo.{table_name}\n\nNo detailed documentation available.\n"

    table_def = TABLE_DEFINITIONS[table_name]

    doc = f"TABLE: dbo.{table_name}\n"
    doc += f"CATEGORY: {table_def.get('category', 'general')}\n"
    doc += f"PRIORITY: {table_def.get('priority', 1)}\n\n"

    # Description
    doc += f"DESCRIPTION:\n{table_def['description']}\n\n"

    # Business Context
    if "business_context" in table_def:
        doc += f"BUSINESS CONTEXT:\n{table_def['business_context']}\n\n"

    # Key Columns
    if "key_columns" in table_def:
        doc += "KEY COLUMNS:\n"
        for category, columns in table_def["key_columns"].items():
            doc += f"\n  [{category.upper()}]\n"
            for col_name, col_desc in columns.items():
                doc += f"    {col_name}: {col_desc}\n"
        doc += "\n"

    # Important Filters
    if "important_filters" in table_def:
        doc += "IMPORTANT FILTERS:\n"
        for filter_example in table_def["important_filters"]:
            doc += f"  {filter_example}\n"
        doc += "\n"

    # Relationships
    if "relationships" in table_def:
        doc += "RELATIONSHIPS:\n"
        for rel in table_def["relationships"]:
            doc += f"  {rel}\n"
        doc += "\n"

    # Notes/Warnings
    if "note" in table_def:
        doc += f"NOTE: {table_def['note']}\n\n"

    if "important_note" in table_def:
        doc += f"IMPORTANT: {table_def['important_note']}\n\n"

    return doc
