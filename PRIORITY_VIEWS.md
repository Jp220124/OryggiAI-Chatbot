# Priority Database Views for SQL Generation

## Summary
**Total Views: 130**  
**Priority Views Identified: 12**

Based on comprehensive analysis, these views provide pre-joined, optimized queries for the most common use cases.

---

## 🎯 TIER 1: CRITICAL VIEWS (Must Index)

### 1. **XXXvw_EmployeeDetail**
**Purpose:** Complete employee information with full organizational hierarchy and attendance  
**Use Cases:**
- Employee details with department
- Organizational hierarchy queries
- Attendance with employee info
- Department-wise employee counts

**Example Queries:**
```sql
-- Top 5 departments with most employees
SELECT TOP 5 Dname, COUNT(*) as cnt
FROM XXXvw_EmployeeDetail
WHERE Active = 1
GROUP BY Dname, Dcode
ORDER BY cnt DESC

-- Employees in specific department
SELECT CorpEmpCode, EmpName, SecName
FROM XXXvw_EmployeeDetail
WHERE Dname = 'IT Department' AND Active = 1
```

---

### 2. **vw_RawPunchDetail**
**Purpose:** Raw punch records with full context  
**Use Cases:**
- Employee punch in/out records
- Attendance tracking
- Time tracking queries

**Example Queries:**
```sql
-- Today's punches
SELECT *
FROM vw_RawPunchDetail
WHERE CAST(PunchTime AS DATE) = CAST(GETDATE() AS DATE)

-- Punch records for an employee
SELECT *
FROM vw_RawPunchDetail
WHERE CorpEmpCode = 'EMP001'
ORDER BY PunchTime DESC
```

---

### 3. **View_ComapnyMaster**
**Purpose:** Complete organizational hierarchy (Employee → Section → Dept → Branch → Company)  
**Use Cases:**
- Company/Branch-wide queries
- Organizational structure reports  
- Multi-level aggregations

**Example Queries:**
```sql
-- Employees per company
SELECT CName, COUNT(*) as EmployeeCount
FROM View_ComapnyMaster
GROUP BY CName

-- Department distribution by branch
SELECT BranchCode, Dcode, COUNT(*) as cnt
FROM View_ComapnyMaster
GROUP BY BranchCode, Dcode
```

---

### 4. **View_BDW_MPunch**
**Purpose:** Employee + Department + Machine Punch (already includes correct joins!)  
**Use Cases:**
- Department-wise punch analysis
- Device/location-based attendance
- Employee punch with dept context

**Example Queries:**
```sql
-- Punches by department today
SELECT Dname, COUNT(*) as PunchCount
FROM View_BDW_MPunch
WHERE CAST(PunchTime AS DATE) = CAST(GETDATE() AS DATE)
GROUP BY Dname

-- Employee punches with department
SELECT EmployeeID, EmpName, Dname, PunchTime, PunchLocation
FROM View_BDW_MPunch
WHERE EmployeeID = 'EMP001'
```

---

## 🔧 TIER 2: IMPORTANT VIEWS (Should Index)

### 5. **vw_EmployeeDetail** / **vw_EmployeeDetail2**
**Purpose:** Detailed employee information (6 joins)  
**Use Cases:** Comprehensive employee queries with related data

---

### 6. **View_MPunch / View_MPunchV3 / View_MpunchV4**
**Purpose:** Machine punch records with employee and organizational details  
**Use Cases:**
- Punch analysis with full context
- Real-time attendance monitoring
- Device-wise punch reports

---

### 7. **vw_Attendanceregister** / **vw_CompleteAttendanceReport**
**Purpose:** Attendance records with employee info  
**Use Cases:**
- Daily attendance reports
- Attendance status queries
- Leave/absence tracking

---

### 8. **View_EmployeeByUserGroupPolicy**
**Purpose:** Complete employee info with policies and biometric status  
**Use Cases:**
- Policy-based queries
- Access control queries
- Biometric enrollment status

---

## 📊 TIER 3: SPECIALIZED VIEWS (Index if relevant)

### Attendance & Time Tracking
- `View_ForExcelExport` - Attendance export format
- `View_HalfDayPresent` - Half-day attendance
- `View_TodayPresentChart` - Today's attendance summary
- `View_TotalAbsentChart` - Absence tracking
- `View_TotalLateArrive` - Late arrival tracking
- `View_TotalEarlyDeparture` - Early departure tracking

### Visitor Management
- `View_VisitorLog` - Visitor records
- `View_SearchVisitor` - Visitor search
- `vw_VisitorBasicDetail` - Basic visitor info

### Access Control
- `View_Employee_Terminal_Authentication_Relation` - Employee access permissions
- `View_Group_By_DCode` - Access groups by department

### Analytics & Aggregations
- `View_TodayAVGINTime` - Average in-time today
- `View_TodayAVGWorkHour` - Average work hours
- `View_TotalEmployeeChart_V2` - Employee count metrics
- `View_TodayPresentDeptWiseChart` - Dept-wise presence

### Other
- `View_Contractor_Detail` - Contractor information
- `View_EmployeeESIPF` - ESIC/PF details
- `vw_EmployeeMaster_Vms` - VMS employee master(18 joins!)

---

## 🎬 IMPLEMENTATION STRATEGY

### Phase 1: Index Critical Views (Tier 1)
1. Update `schema_extractor.py` to extract views
2. Update `schema_enricher.py` to include view metadata
3. Re-index with priority views: `XXXvw_EmployeeDetail`, `vw_RawPunchDetail`, `View_ComapnyMaster`, `View_BDW_MPunch`

### Phase 2: Update SQL Agent
1. Add prompt rules to prefer views over tables
2. Add view usage guidelines
3. Update few-shot examples to use views

### Phase 3: Comprehensive Coverage
1. Index Tier 2 views for broader coverage
2. Index specialized Tier 3 views as needed
3. Monitor query patterns and adjust

---

## 📋 VIEW SELECTION CRITERIA

When choosing which view to use:

1. **Prefer simpler views** - Fewer joins = better performance
2. **Match use case** - Use specialized views for specific queries
3. **Check column availability** - Ensure view has required columns
4. **Consider freshness** - Some views may cache data

---

## ⚠️ IMPORTANT NOTES

- **View naming inconsistency**: Some use `View_`, others use `vw_`, some use `VW_`, `Vw_`
- **Most complex view**: `vw_EmployeeMaster_Vms` (18 joins!) - use only when all that data is needed
- **Department hierarchy**: Always use SectionMaster → DeptMaster pattern (already in views)
- **Never use** `EmpDepartRole` table directly - it's empty!

---

## 🔍 COVERAGE MAP

| Query Type | Recommended View |
|------------|-----------------|
| Employee + Department | `XXXvw_EmployeeDetail` |
| Punch Records | `vw_RawPunchDetail` |
| Org Hierarchy | `View_ComapnyMaster` |
| Dept + Punches | `View_BDW_MPunch` |
| Complete Employee Info | `vw_EmployeeDetail` |
| Machine Punches | `View_MPunch` / `View_MPunchV3` |
| Attendance | `vw_Attendanceregister` |
| Visitors | `View_VisitorLog` |
| Analytics/Charts | `View_Today*` series |

---

**Next Steps:**
1. Update schema extraction to include views
2. Create few-shot examples using these views
3. Update SQL agent prompt with view preferences
4. Test with common queries
