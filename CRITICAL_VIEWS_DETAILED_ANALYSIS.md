# CRITICAL DATABASE VIEWS - COMPREHENSIVE ANALYSIS & RECOMMENDATIONS

> **Purpose:** Deep analysis of 9 user-specified critical views for SQL generation optimization

---

## Executive Summary

**Total Views Analyzed:** 9 critical views  
**Complexity Range:** Simple UNIONs to 18-table JOINs  
**Key Finding:** These views cover **ALL major use cases** - Employees, Contractors, Visitors, Punch Records, Terminal Authentication, and VMS integration

---

## 1. EMPLOYEE VIEWS (Core)

### 1.1 AllEmployeeUnion ⭐⭐⭐⭐⭐
**Priority:** CRITICAL - Use this for ALL employee queries

**Purpose:** Combines active AND deleted employees into single queryable view

**Structure:**
- Simple UNION of `EmployeeMaster` and `EmployeeMaster_Deleted`
- **72 columns** covering complete employee data

**Base Tables:**
- `EmployeeMaster`
- `EmployeeMaster_Deleted`

**Use Cases:**
✅ **ANY employee-related query** should use this  
✅ Historical employee lookups  
✅ Employee counts (active + deleted)  
✅ Employee lists with all attributes  

**Example Queries:**
```sql
-- Better than querying EmployeeMaster alone
SELECT COUNT(*) FROM dbo.AllEmployeeUnion WHERE Active = 1
SELECT * FROM dbo.AllEmployeeUnion WHERE SecCode = 'SEC001'
SELECT EmpName FROM dbo.AllEmployeeUnion WHERE Role = 'Employee'
```

**Why It Matters:**
This view ensures we capture ALL employees, not just active ones. Critical for historical reporting.

---

### 1.2 vw_EmployeeMaster_Vms ⭐⭐⭐⭐⭐
**Priority:** CRITICAL - Most comprehensive employee view

**Purpose:** Complete employee details with org hierarchy, biometrics, contractor info, attendance, and user groups

**Complexity:** **18 INNER/LEFT JOINs**

**Base Tables (16 total):**
- CompanyMaster → BranchMaster → DeptMaster → SectionMaster → EmployeeMaster (org hierarchy)
- CatMaster, DesignationMaster, GradeMaster, RoleMaster (classifications)
- View_Contractor_Detail (contractor info)
- FingerMaster (biometric mappings)
- AttendanceRegister (today's attendance)
- Biometric (enrollment status: Finger, Face, LeftHand, RightHand, Card)
- Employee_Terminal_Authentication_Relation (card authentication)
- UserGroupPolicy, Vedanta_User_Category_RTL (user groups & plants)

**Key Features:**
- ✅ Complete org hierarchy (Company → Branch → Dept → Section)
- ✅ Employee classifications (Category, Designation, Grade)
- ✅ Biometric enrollment status (Face, Finger, Card detection)
- ✅ Today's attendance (InTime, OutTime)
- ✅ Contractor details (PO Number, Name)
- ✅ Reporting head information
- ✅ User group memberships (comma-separated PlantIDs, UserGroupIDs)

**Filters:**
- Excludes 'Admin' user
- Excludes Visitors (Role <> 'Visitor')

**Use Cases:**
✅ Employee master reports with full details  
✅ VMS system employee synchronization  
✅ Biometric enrollment status queries  
✅ Employee organizational hierarchy queries  
✅ Contractor employee queries  
✅ Today's attendance queries  

**Example Queries:**
```sql
-- Get all employees with biometric status
SELECT CorpEmpCode, EmpName, Finger, Face, Card FROM dbo.vw_EmployeeMaster_Vms

-- Employees by department with attendance
SELECT Dname, CorpEmpCode, EmpName, InTime, OutTime 
FROM dbo.vw_EmployeeMaster_Vms 
WHERE Dcode = 'DEPT001'

-- Contractor employees
SELECT Name, CorpEmpCode, EmpName, PO_Number 
FROM dbo.vw_EmployeeMaster_Vms 
WHERE ContractorID IS NOT NULL
```

---

### 1.3 View_EmployeeByUserGroupPolicy ⭐⭐⭐⭐
**Priority:** HIGH - For user group and biometric queries

**Purpose:** Employee details filtered/enriched by user group policies with biometric enrollment

**Complexity:** Multiple subqueries for biometric checks

**Base Tables:**
- CompanyMaster → BranchMaster → DeptMaster → SectionMaster → EmployeeMaster
- CatMaster, DesignationMaster, GradeMaster, FingerMaster
- StatusMaster
- View_Contractor_Detail
- PinMaster
- Biometric (multiple subqueries for Finger, LeftHand, RightHand, Face detection)

**Key Features:**
- ✅ Biometric enrollment flags (Finger, LeftHand, RightHand, Face)
- ✅ PIN/Password information
- ✅ Status information
- ✅ Complete org hierarchy

**Use Cases:**
✅ User group policy management  
✅ Biometric enrollment queries  
✅ Access control queries  
✅ PIN management  

---

## 2. PUNCH RECORD VIEWS

### 2.1 vw_RawPunchDetail ⭐⭐⭐⭐⭐
**Priority:** CRITICAL - For ALL punch/attendance queries

**Purpose:** Pre-joined view of raw punch records with employee and machine details

**Complexity:** Complex multi-table JOIN (9 base tables)

**Base Tables:**
- BranchMaster → DeptMaster → SectionMaster → AllEmployeeUnion (org hierarchy)
- AllEmployeeUnion → EmployeeMaster (employee details + image)
- AllEmployeeUnion → DesignationMaster (designation)
- MachineRawPunch → MachineMaster (punch events + machine info)
- AuthenticationMaster (via subquery for authentication method)

**Key Columns:**
- **Punch Info:** CardNo, PunchTime, ATDate, InOut, IsManual, TransactionId
- **Employee:** ECode, CorpEmpCode, EmpName, Image, Role, StatusID
- **Organization:** Dcode, Dname, BranchCode, Ccode, SecCode, DesCode, DesName
- **Machine:** MachineID, TerminalID, Location, IPAddress, DomainName
- **Authentication:** Authentication method (Face, Card, Finger, etc.)

**Use Cases:**
✅ **Primary view for punch record queries**  
✅ Attendance report generation  
✅ Punch history by employee  
✅ Machine-wise punch analysis  
✅ Authentication method analysis  
✅ Department-wise punch tracking  

**Example Queries:**
```sql
-- Punches by department
SELECT Dname, COUNT(*) as PunchCount 
FROM dbo.vw_RawPunchDetail 
WHERE ATDate = '2025-01-20'
GROUP BY Dname

-- Employee punch history
SELECT PunchTime, InOut, Location, Authentication 
FROM dbo.vw_RawPunchDetail 
WHERE CorpEmpCode = 'EMP001'
ORDER BY PunchTime DESC

-- Manual punches
SELECT EmpName, Dname, PunchTime, Authentication
FROM dbo.vw_RawPunchDetail 
WHERE IsManual = 1
```

**Why It Matters:**
This single view eliminates the need to manually join MachineRawPunch with 8 other tables. Critical for performance.

---

## 3. VISITOR MANAGEMENT VIEWS

### 3.1 View_Visitor_EnrollmentDetail ⭐⭐⭐⭐
**Priority:** HIGH - For visitor management

**Purpose:** Complete visitor enrollment details with organizational context

**Base Tables (9 total):**
- Vistor_Details (alias V) → EmployeeMaster (alias M)
- CompanyMaster, BranchMaster, DeptMaster, SectionMaster (org hierarchy)
- PurposeMaster, IDProofMaster, AreaGroupMaster

**Key Columns:**
- **Visitor:** Ecode, CorpEmpCode, FName, LName, Image, MobileNumber, OTP
- **Visit Details:** Whom_To_Visit, Purpose, Expected_IN_Time, IN_Time, Expected_OUT_Time, OUT_Time
- **ID Proof:** ID_Proof_Type, ID_Proof_Detail, ID_Proof_Image
- **Card:** Issued_Card_Number, Status
- **Organization:** Company, Branch, Department, Section of host
- **Vehicle:** Vachel_Number, Document_Detail

**Use Cases:**
✅ Visitor check-in/check-out  
✅ Visitor pass issuance  
✅ Visitor history  
✅ Security clearance tracking  

---

### 3.2 vw_VisitorBasicDetail ⭐⭐⭐
**Priority:** MEDIUM - Simplified visitor view

**Purpose:** Basic visitor information (simpler than View_Visitor_EnrollmentDetail)

**Base Tables:**
- Vistor_Details
- EmployeeMaster

**Use Cases:**
✅ Quick visitor lookups  
✅ Visitor lists  

---

### 3.3 vw_EmployeeMaster_Vms ⭐⭐⭐
**Priority:** MEDIUM - VMS-specific visitor view

**Purpose:** Likely related to Visitor Management System (VMS) integration

**Note:** Already covered in Employee Views section above

---

## 4. CONTRACTOR VIEWS

### 4.1 View_Contractor_Detail ⭐⭐⭐⭐
**Priority:** HIGH - For contractor management

**Purpose:** Contractor master data with job/contract details

**Base Tables:**
- ContractorMaster
- Contractor_Detail

**Key Columns:**
- **Contractor:** ContractorID, Contractor_Code, Name, Address, Email, Mobile
- **Contract:** Client_ID, PO_Number, PO_Date, Job_Detail, Service_Start_Date

**Use Cases:**
✅ Contractor employee queries (used by vw_EmployeeMaster_Vms)  
✅ Contractor management  
✅ PO tracking  
✅ Contract expiry monitoring  

---

## 5. TERMINAL AUTHENTICATION VIEWS

### 5.1 View_Employee_Terminal_Authentication_Relation ⭐⭐⭐⭐
**Priority:** HIGH - For access control

**Purpose:** Employee-terminal authentication mappings with access schedules

**Base Tables (5 total):**
- Employee_Terminal_Authentication_Relation
- EmployeeMaster
- MachineMaster
- AuthenticationMaster
- Access_Schedules

**Key Columns:**
- **Employee:** CorpEmpCode, Ecode
- **Terminal:** IPAddress, DeviceType, Location, DomainName
- **Authentication:** AuthenticationName (Face, Card, PIN, etc.)
- **Access:** Schedule_Name, WhiteList, VIP_list_flag

**Use Cases:**
✅ Access control management  
✅ Terminal assignment  
✅ Authentication method configuration  
✅ Whitelist/VIP management  
✅ Access schedule queries  

---

### 5.2 Vw_TerminalDetail_VMS ⭐⭐⭐
**Priority:** MEDIUM - Terminal configuration for VMS

**Purpose:** Complete terminal/machine configuration details for VMS integration

**Base Tables:**
- MachineMaster
- Vw_CompanyBranchDepartmentDetail_VMS (nested view)
- WiegandMaster
- DataConnectionOutputTypeMaster
- IOModuleTyp

**Key Columns:**
- **Terminal:** MachineID, DeviceType, TerminalID, IPAddress, Location, PortNo
- **Connection:** Connectiontype, comboAppProtocol, Connection_Status, Configuration
- **Wiegand:** Wiegand settings for card readers
- **Organization:** Company, Branch, Department details

**Use Cases:**
✅ VMS terminal management  
✅ Device configuration  
✅ Connection monitoring  
✅ Wiegand card reader setup  

---

## PRIORITY RANKING FOR SQL GENERATION

### 🥇 Tier 1: ALWAYS USE (Critical)
1. **AllEmployeeUnion** - For ANY employee query
2. **vw_RawPunchDetail** - For ANY punch/attendance query
3. **vw_EmployeeMaster_Vms** - For complete employee details with biometrics

### 🥈 Tier 2: FREQUENTLY USE (High Priority)
4. **View_Visitor_EnrollmentDetail** - For visitor queries
5. **View_Contractor_Detail** - For contractor queries
6. **View_Employee_Terminal_Authentication_Relation** - For access control
7. **View_EmployeeByUserGroupPolicy** - For user group queries

### 🥉 Tier 3: SPECIALIZED USE
8. **Vw_TerminalDetail_VMS** - VMS terminal configuration
9. **vw_VisitorBasicDetail** - Simple visitor lookups

---

## RECOMMENDATIONS FOR SQL AGENT

### 1. Schema Indexing Priority
```python
CRITICAL_VIEWS = [
    'AllEmployeeUnion',           # Use for ALL employee queries
    'vw_RawPunchDetail',          # Use for ALL punch queries
    'vw_EmployeeMaster_Vms',      # Complete employee + biometric + attendance
]

HIGH_PRIORITY_VIEWS = [
    'View_Visitor_EnrollmentDetail',
    'View_Contractor_Detail',
    'View_Employee_Terminal_Authentication_Relation',
    'View_EmployeeByUserGroupPolicy'
]
```

### 2. SQL Generation Rules

**Rule 1:** Prefer views over manual JOINs
```sql
-- ❌ DON'T DO THIS:
SELECT e.*, d.Dname FROM EmployeeMaster e 
INNER JOIN SectionMaster s ON e.SecCode = s.SecCode
INNER JOIN DeptMaster d ON s.Dcode = d.Dcode

-- ✅ DO THIS INSTEAD:
SELECT CorpEmpCode, EmpName, Dname FROM dbo.vw_EmployeeMaster_Vms
```

**Rule 2:** Use AllEmployeeUnion for employee counts/lists
```sql
-- ❌ DON'T:
SELECT COUNT(*) FROM EmployeeMaster WHERE Active = 1

-- ✅ DO:
SELECT COUNT(*) FROM AllEmployeeUnion WHERE Active = 1
```

**Rule 3:** Use vw_RawPunchDetail for punch queries
```sql
-- ❌ DON'T:
SELECT m.PunchTime FROM MachineRawPunch m 
INNER JOIN EmployeeMaster e ON m.ECode = e.Ecode

-- ✅ DO:
SELECT PunchTime, EmpName, Dname FROM vw_RawPunchDetail
```

### 3. Few-Shot Examples to Add

```python
CRITICAL_FEW_SHOTS = [
    {
        "question": "How many employees are in each department?",
        "sql": "SELECT Dname, COUNT(*) as EmployeeCount FROM dbo.vw_EmployeeMaster_Vms WHERE Active = 1 GROUP BY Dname ORDER BY EmployeeCount DESC"
    },
    {
        "question": "Show me punch records from yesterday",
        "sql": "SELECT CorpEmpCode, EmpName, PunchTime, InOut, Location FROM dbo.vw_RawPunchDetail WHERE CAST(ATDate AS DATE) = CAST(DATEADD(day, -1, GETDATE()) AS DATE) ORDER BY PunchTime"
    },
    {
        "question": "List all active employees with their biometric status",
        "sql": "SELECT CorpEmpCode, EmpName, Dname, Finger, Face, Card FROM dbo.vw_EmployeeMaster_Vms WHERE Active = 1"
    },
    {
        "question": "Show visitors who checked in today",
        "sql": "SELECT FName, LName, Whom_To_Visit, IN_Time, Purpose FROM dbo.View_Visitor_EnrollmentDetail WHERE CAST(IN_Time AS DATE) = CAST(GETDATE() AS DATE)"
    }
]
```

---

## ACTIONABLE NEXT STEPS

### Step 1: Update Priority Views List
Update `schema_extractor.py` to use this comprehensive list:

```python
PRIORITY_VIEWS = [
    # Tier 1: Critical
    'AllEmployeeUnion',
    'vw_RawPunchDetail',
    'vw_EmployeeMaster_Vms',
    
    # Tier 2: High Priority  
    'View_Visitor_EnrollmentDetail',
    'View_Contractor_Detail',
    'View_Employee_Terminal_Authentication_Relation',
    'View_EmployeeByUserGroupPolicy',
    
    # Tier 3: Specialized
    'Vw_TerminalDetail_VMS',
    'vw_VisitorBasicDetail'
]
```

### Step 2: Update SQL Agent System Prompt
Add explicit rules to prefer these views

### Step 3: Create Few-Shot Examples
Add examples using these views to FAISS index

### Step 4: Re-index Schema
Run the reindexing script to add these views

---

## CONCLUSION

These 9 views provide **comprehensive coverage** of the entire system:
- ✅ Employees (all statuses) - AllEmployeeUnion
- ✅ Employee details - vw_EmployeeMaster_Vms  
- ✅ Punch records - vw_RawPunchDetail
- ✅ Visitors - View_Visitor_EnrollmentDetail
- ✅ Contractors - View_Contractor_Detail
- ✅ Access control - View_Employee_Terminal_Authentication_Relation
- ✅ Terminals - Vw_TerminalDetail_VMS

**Using these views will:**
1. ✅ Eliminate complex manual JOINs
2. ✅ Improve query performance
3. ✅ Reduce SQL generation errors
4. ✅ Ensure correct table relationships
5. ✅ Enable faster development

**Priority Action:** Update the priority views list and re-index immediately!
