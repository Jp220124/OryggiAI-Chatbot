-- View: View_EmployeeByUserGroupPolicy
-- ------------------------------------------------------------------------------

 

CREATE VIEW [dbo].[View_EmployeeByUserGroupPolicy]

AS

SELECT        dbo.EmployeeMaster.Ecode, dbo.EmployeeMaster.CorpEmpCode, dbo.EmployeeMaster.Active, dbo.EmployeeMaster.SecCode, dbo.EmployeeMaster.EmpName, dbo.EmployeeMaster.DateofJoin, 

                         dbo.EmployeeMaster.PresentCardNo, dbo.DeptMaster.Dcode, dbo.CompanyMaster.Ccode, dbo.BranchMaster.BranchCode, dbo.EmployeeMaster.Gcode, dbo.EmployeeMaster.Catcode, dbo.EmployeeMaster.DesCode, 

                         dbo.CompanyMaster.CName, dbo.BranchMaster.BranchName, dbo.DeptMaster.Dname, dbo.SectionMaster.SecName, dbo.CatMaster.CatName, dbo.DesignationMaster.DesName, dbo.GradeMaster.Gname, 

                         dbo.FingerMaster.FingerName AS Finger1, FingerMaster_1.FingerName AS Finger2, dbo.EmployeeMaster.IsEnrolled, dbo.EmployeeMaster.GuardianName, dbo.EmployeeMaster.DateofBirth, dbo.EmployeeMaster.Sex, 

                         dbo.EmployeeMaster.IsMarried, dbo.EmployeeMaster.Qualification, dbo.EmployeeMaster.Experience, dbo.EmployeeMaster.Address1, dbo.EmployeeMaster.Telephone1, dbo.EmployeeMaster.E_mail, 

                         dbo.EmployeeMaster.Address2, dbo.EmployeeMaster.Telephone2, dbo.EmployeeMaster.BloodGroup, dbo.EmployeeMaster.LeavingDate, dbo.EmployeeMaster.LeavingReason, dbo.EmployeeMaster.Password, 

                         dbo.EmployeeMaster.Role, dbo.EmployeeMaster.DefaultPolicy, dbo.EmployeeMaster.PermissableLateArrival, dbo.EmployeeMaster.PermissbleeEarlyDeparture, dbo.EmployeeMaster.MinWorkHourForPresent, 

                         dbo.EmployeeMaster.IsHalfDayAllowed, dbo.EmployeeMaster.MinWorkHourForHalfDay, dbo.EmployeeMaster.IsShortDayAllowed, dbo.EmployeeMaster.OvertimeAllowed, dbo.EmployeeMaster.MinWorkHourForShortDay, 

                         dbo.EmployeeMaster.MinDurationReqForOvertime, dbo.EmployeeMaster.OnePunchPresentMarking, dbo.EmployeeMaster.FWOAssigned, dbo.EmployeeMaster.FirstWO, dbo.EmployeeMaster.SWOAssigned, 

                         dbo.EmployeeMaster.SWO, dbo.EmployeeMaster.SWOFirst, dbo.EmployeeMaster.SWOSecond, dbo.EmployeeMaster.SWOThird, dbo.EmployeeMaster.SWOFourth, dbo.EmployeeMaster.SWOFifth, 

                         dbo.EmployeeMaster.SWOType, dbo.EmployeeMaster.Image, dbo.EmployeeMaster.WorkMinuteFomula, dbo.EmployeeMaster.ESINo, dbo.EmployeeMaster.IsBlackListed, dbo.EmployeeMaster.ReportingHeadEcode, 

                         dbo.EmployeeMaster.FP1_ID, dbo.EmployeeMaster.FP2_ID, dbo.EmployeeMaster.DFP_ID, dbo.EmployeeMaster.FName, dbo.EmployeeMaster.LName, dbo.EmployeeMaster.WiegandValue, dbo.EmployeeMaster.LastUpdate, 

                         dbo.EmployeeMaster.LoginAuthenticationID, dbo.EmployeeMaster.ContarctManualEndDate, dbo.EmployeeMaster.StatusID, dbo.StatusMaster.StatusName, dbo.View_Contractor_Detail.Name, 

                         dbo.View_Contractor_Detail.ContractorID, dbo.View_Contractor_Detail.PO_Number, dbo.PinMaster.Pin, dbo.EmployeeMaster.[2DStatus], CASE WHEN

                             (SELECT        COUNT(*)

                               FROM            Biometric AS BT

                               WHERE        [Format] IN (1, 2, 3, 6, 402) AND FingerID IN (1, 2, 3, 4, 5, 6, 7, 8, 9, 10) AND BT.Ecode = EmployeeMaster.Ecode) > 0 THEN 'YES' ELSE 'NO' END AS Finger, CASE WHEN

                             (SELECT        COUNT(*)

                               FROM            Biometric AS BT

                               WHERE        [Format] IN (203, 206) AND FingerID IN (1, 2, 3, 4) AND BT.Ecode = EmployeeMaster.Ecode) > 0 THEN 'YES' ELSE 'NO' END AS LeftHand, CASE WHEN

                             (SELECT        COUNT(*)

                               FROM            Biometric AS BT

                               WHERE        [Format] IN (203, 206) AND FingerID IN (7, 8, 9, 10) AND BT.Ecode = EmployeeMaster.Ecode) > 0 THEN 'YES' ELSE 'NO' END AS RightHand, CASE WHEN

                             (SELECT        COUNT(*)

                               FRO