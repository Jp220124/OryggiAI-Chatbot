# CRITICAL DATABASE VIEWS - DETAILED ANALYSIS
================================================================================


## vw_RawPunchDetail
--------------------------------------------------------------------------------

**Complexity:**
- JOINs: 0
- Base Tables: 9

**Tables Referenced:**
  - AllEmployeeUnion
  - AuthenticationMaster
  - BranchMaster
  - DeptMaster
  - DesignationMaster
  - EmployeeMaster
  - MachineMaster
  - MachineRawPunch
  - SectionMaster

**SQL Definition (truncated to 500 chars):**
```sql


CREATE VIEW [dbo].[vw_RawPunchDetail]

AS

SELECT  TOP (100) PERCENT dbo.MachineRawPunch.CardNo, CONVERT(datetime, dbo.MachineRawPunch.PunchTime, 106) AS ATDate, dbo.MachineRawPunch.PunchTime, dbo.MachineRawPunch.IsManual, 

            dbo.MachineRawPunch.TransactionId, dbo.MachineRawPunch.InOut, dbo.MachineMaster.Location, dbo.EmployeeMaster.Image, dbo.MachineRawPunch.ECode, dbo.AllEmployeeUnion.CorpEmpCode, 

            dbo.AllEmployeeUnion.EmpName, dbo.AllEmployeeUnion.SecCode, dbo.Sectio...
```

**Full definition saved to:** `view_def_vw_RawPunchDetail.sql`



## AllEmployeeUnion
--------------------------------------------------------------------------------

**Complexity:**
- JOINs: 0
- Base Tables: 2

**Tables Referenced:**
  - EmployeeMaster
  - EmployeeMaster_Deleted

**SQL Definition (truncated to 500 chars):**
```sql
CREATE VIEW [dbo].[AllEmployeeUnion]

AS

SELECT        [Ecode], [CorpEmpCode], [Active], [Gcode], [Catcode], [DesCode], [SecCode], [EmpName], [GuardianName], [DateofBirth], [DateofJoin], [PresentCardNo], [Sex], [IsMarried], [Qualification], [Experience], [Address1], [Telephone1], 

                         [E_mail], [Address2], [Telephone2], [BloodGroup], [LeavingDate], [LeavingReason], [Password], [Role], [DefaultPolicy], [PermissableLateArrival], [PermissbleeEarlyDeparture], [MinWorkHourForPr...
```

**Full definition saved to:** `view_def_AllEmployeeUnion.sql`



## View_Contractor_Detail
--------------------------------------------------------------------------------

**Complexity:**
- JOINs: 0
- Base Tables: 2

**Tables Referenced:**
  - ContractorMaster
  - Contractor_Detail

**SQL Definition (truncated to 500 chars):**
```sql


Create VIEW [dbo].[View_Contractor_Detail]

AS

SELECT        dbo.ContractorMaster.ContractorID, dbo.ContractorMaster.Contractor_Code, dbo.ContractorMaster.Name, dbo.ContractorMaster.Address, dbo.ContractorMaster.Email, dbo.ContractorMaster.Mobile, 

                         dbo.ContractorMaster.Description, dbo.Contractor_Detail.Client_ID, dbo.Contractor_Detail.PO_Number, dbo.Contractor_Detail.PO_Date, dbo.Contractor_Detail.Job_Detail, dbo.Contractor_Detail.Servce_Start_Date, 

              ...
```

**Full definition saved to:** `view_def_View_Contractor_Detail.sql`



## View_Employee_Terminal_Authentication_Relation
--------------------------------------------------------------------------------

**Complexity:**
- JOINs: 0
- Base Tables: 5

**Tables Referenced:**
  - Access_Schedules
  - AuthenticationMaster
  - EmployeeMaster
  - Employee_Terminal_Authentication_Relation
  - MachineMaster

**SQL Definition (truncated to 500 chars):**
```sql
CREATE VIEW [dbo].[View_Employee_Terminal_Authentication_Relation]

AS

SELECT        dbo.EmployeeMaster.CorpEmpCode, dbo.EmployeeMaster.Ecode, dbo.MachineMaster.IPAddress, dbo.MachineMaster.DeviceType, dbo.MachineMaster.Location, dbo.MachineMaster.DomainName, 

                         dbo.AuthenticationMaster.AuthenticationName, dbo.Access_Schedules.Schedule_Name, dbo.Employee_Terminal_Authentication_Relation.WhiteList, dbo.Employee_Terminal_Authentication_Relation.VIP_list_flag, 

           ...
```

**Full definition saved to:** `view_def_View_Employee_Terminal_Authentication_Relation.sql`



## View_Visitor_EnrollmentDetail
--------------------------------------------------------------------------------

**Complexity:**
- JOINs: 0
- Base Tables: 9

**Tables Referenced:**
  - AreaGroupMaster
  - BranchMaster
  - CompanyMaster
  - DeptMaster
  - EmployeeMaster
  - IDProofMaster
  - PurposeMaster
  - SectionMaster
  - Vistor_Details

**SQL Definition (truncated to 500 chars):**
```sql
CREATE VIEW [dbo].[View_Visitor_EnrollmentDetail]

AS

SELECT        M.Ecode, V.CorpEmpCode, V.FName, V.LName, M.Image, M.Whom_To_Visit, 

                         M.Expected_IN_Time, M.IN_Time, M.Expected_OUT_Time, M.OUT_Time, M.Purpose, M.ID_Proof_Type, 

                         M.ID_Proof_Detail, M.ID_Proof_Image, M.MobileNumner, M.OTP, M.Issued_Card_Number, M.Status, 

                         M.TermnalGroupID, M.Document_Detail, M.Vachel_Number, M.Create_Time, V.Role, 

                   ...
```

**Full definition saved to:** `view_def_View_Visitor_EnrollmentDetail.sql`



## vw_EmployeeMaster_Vms
--------------------------------------------------------------------------------

**Complexity:**
- JOINs: 18
- Base Tables: 16

**Tables Referenced:**
  - AttendanceRegister
  - Biometric
  - BranchMaster
  - CatMaster
  - CompanyMaster
  - DeptMaster
  - DesignationMaster
  - EmployeeMaster
  - Employee_Terminal_Authentication_Relation
  - FingerMaster
  - GradeMaster
  - RoleMaster
  - SectionMaster
  - UserGroupPolicy
  - Vedanta_User_Category_RTL
  - View_Contractor_Detail

**SQL Definition (truncated to 500 chars):**
```sql
CREATE VIEW [dbo].[vw_EmployeeMaster_Vms]

AS

SELECT  E.Ecode, E.CorpEmpCode, E.Active, E.SecCode, E.EmpName, E.DateofJoin, E.PresentCardNo, D.Dcode, C.Ccode, B.BranchCode, E.Gcode, E.Catcode, E.DesCode, 

		C.CName, B.BranchName, D.Dname, S.SecName, CAT.CatName, DES.DesName, G.Gname, F.FingerName AS Finger1, F2.FingerName AS Finger2, E.IsEnrolled, 

		E.GuardianName, E.DateofBirth, E.Sex, E.IsMarried, E.Qualification, E.Experience, E.Address1, E.Telephone1, E.Latitude, E.Longitude, E.E_mail, E...
```

**Full definition saved to:** `view_def_vw_EmployeeMaster_Vms.sql`



## Vw_TerminalDetail_VMS
--------------------------------------------------------------------------------

**Complexity:**
- JOINs: 0
- Base Tables: 5

**Tables Referenced:**
  - DataConnectionOutputTypeMaster
  - IOModuleTyp
  - MachineMaster
  - Vw_CompanyBranchDepartmentDetail_VMS
  - WiegandMaster

**SQL Definition (truncated to 500 chars):**
```sql
CREATE VIEW [dbo].[Vw_TerminalDetail_VMS]

AS

SELECT        dbo.MachineMaster.MachineID, dbo.MachineMaster.DeviceType, dbo.MachineMaster.TerminalID, dbo.MachineMaster.IPAddress, dbo.MachineMaster.DomainName, dbo.MachineMaster.PortNo, dbo.MachineMaster.Location, 

                         dbo.MachineMaster.Connectiontype, dbo.MachineMaster.comboAppProtocol, dbo.MachineMaster.Sno, dbo.MachineMaster.LKey, dbo.MachineMaster.Connection_Status, dbo.MachineMaster.Configuration, 

                     ...
```

**Full definition saved to:** `view_def_Vw_TerminalDetail_VMS.sql`



## vw_VisitorBasicDetail
--------------------------------------------------------------------------------

**Complexity:**
- JOINs: 0
- Base Tables: 2

**Tables Referenced:**
  - EmployeeMaster
  - Vistor_Details

**SQL Definition (truncated to 500 chars):**
```sql


---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------



CREATE VIEW [dbo].[vw_VisitorBasicDetail]

AS

SELECT        TOP (100) PERCENT dbo.Vistor_Details.ID, dbo.EmployeeMaster.Ecode...
```

**Full definition saved to:** `view_def_vw_VisitorBasicDetail.sql`



## View_EmployeeByUserGroupPolicy
--------------------------------------------------------------------------------

**Complexity:**
- JOINs: 0
- Base Tables: 1

**Tables Referenced:**
  - Biometric

**SQL Definition (truncated to 500 chars):**
```sql
 

CREATE VIEW [dbo].[View_EmployeeByUserGroupPolicy]

AS

SELECT        dbo.EmployeeMaster.Ecode, dbo.EmployeeMaster.CorpEmpCode, dbo.EmployeeMaster.Active, dbo.EmployeeMaster.SecCode, dbo.EmployeeMaster.EmpName, dbo.EmployeeMaster.DateofJoin, 

                         dbo.EmployeeMaster.PresentCardNo, dbo.DeptMaster.Dcode, dbo.CompanyMaster.Ccode, dbo.BranchMaster.BranchCode, dbo.EmployeeMaster.Gcode, dbo.EmployeeMaster.Catcode, dbo.EmployeeMaster.DesCode, 

                         dbo.Compa...
```

**Full definition saved to:** `view_def_View_EmployeeByUserGroupPolicy.sql`


