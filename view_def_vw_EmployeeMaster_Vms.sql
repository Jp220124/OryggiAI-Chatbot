-- View: vw_EmployeeMaster_Vms
-- ------------------------------------------------------------------------------

CREATE VIEW [dbo].[vw_EmployeeMaster_Vms]

AS

SELECT  E.Ecode, E.CorpEmpCode, E.Active, E.SecCode, E.EmpName, E.DateofJoin, E.PresentCardNo, D.Dcode, C.Ccode, B.BranchCode, E.Gcode, E.Catcode, E.DesCode, 

		C.CName, B.BranchName, D.Dname, S.SecName, CAT.CatName, DES.DesName, G.Gname, F.FingerName AS Finger1, F2.FingerName AS Finger2, E.IsEnrolled, 

		E.GuardianName, E.DateofBirth, E.Sex, E.IsMarried, E.Qualification, E.Experience, E.Address1, E.Telephone1, E.Latitude, E.Longitude, E.E_mail, E.Address2, E.Telephone2, 

		E.BloodGroup, E.LeavingDate, E.LeavingReason, E.Password, E.Role, E.emptype, R.Role AS [AccessType], E.DefaultPolicy, E.PermissableLateArrival, E.PermissbleeEarlyDeparture, 

		E.MinWorkHourForPresent, E.IsHalfDayAllowed, E.MinWorkHourForHalfDay, E.IsShortDayAllowed, E.OvertimeAllowed, E.MinWorkHourForShortDay, 

		E.MinDurationReqForOvertime, E.OnePunchPresentMarking, E.FWOAssigned, E.FirstWO, E.SWOAssigned, E.SWO, E.SWOFirst, E.SWOSecond, E.SWOThird, E.SWOFourth, 

		E.SWOFifth, E.SWOType, E.Image, E.WorkMinuteFomula, E.ESINo, E.IsBlackListed, E.ReportingHeadEcode, E.FP1_ID, E.FP2_ID, E.DFP_ID, E.FName, E.LName, 

		E.WiegandValue, E.LastUpdate, RE.EmpName AS [ReportingHeadName], E.LoginAuthenticationID, E.ContarctManualEndDate, E.StatusID, CONT.Name, 

		CONT.ContractorID, CONT.PO_Number, E.Password2 AS Pin, E.[2DStatus], AT.InTime, AT.OutTime,

		CASE WHEN BT1.Ecode IS NOT NULL THEN 'YES' ELSE 'NO' END AS Finger, CASE WHEN BT2.Ecode IS NOT NULL THEN 'YES' ELSE 'NO' END AS LeftHand,

		CASE WHEN BT3.Ecode IS NOT NULL THEN 'YES' ELSE 'NO' END AS RightHand, CASE WHEN BT4.Ecode IS NOT NULL THEN 'YES' ELSE 'NO' END AS Face,

		CASE WHEN EREL.Ecode IS NOT NULL THEN 'YES' ELSE 'NO' END AS Card,

		STUFF((

			SELECT ',' + CONVERT(VARCHAR(10), EC.PlantID) FROM Vedanta_User_Category_RTL EC WHERE E.Ecode = EC.UserID FOR XML PATH('')

		), 1, 1, '') AS [PlantIDs],

		STUFF((

        SELECT ', ' + CAST(UGP.UserGroupID AS VARCHAR) FROM UserGroupPolicy UGP WHERE UGP.Ecode = E.Ecode FOR XML PATH('')

		), 1, 2, '') AS UserGroupID

FROM    CompanyMaster C 

		INNER JOIN BranchMaster B ON C.Ccode = B.Ccode 

		INNER JOIN DeptMaster D ON B.BranchCode = D.BranchCode 

		INNER JOIN SectionMaster S ON D.Dcode = S.Dcode 

		INNER JOIN EmployeeMaster E ON S.SecCode = E.SecCode 

		INNER JOIN CatMaster CAT ON E.Catcode = CAT.CatCode 

		INNER JOIN DesignationMaster DES ON E.DesCode = DES.DesCode 

		INNER JOIN GradeMaster G ON E.Gcode = G.Gcode 

		INNER JOIN RoleMaster R ON E.emptype = R.RoleId

		LEFT JOIN View_Contractor_Detail CONT ON E.ContractorID = CONT.ContractorID 

		LEFT JOIN FingerMaster F ON E.FP1_ID = F.FingerID 

		LEFT JOIN FingerMaster F2 ON E.FP2_ID = F2.FingerID 

		LEFT JOIN AttendanceRegister AT ON E.Ecode = AT.ECode AND CONVERT(DATE, ATDate) = CONVERT(DATE, GETDATE())

		LEFT JOIN EmployeeMaster RE ON RE.Ecode = E.ReportingHeadEcode

		LEFT JOIN (SELECT DISTINCT Ecode FROM Biometric WHERE [Format] IN (1,2,3,6,402) AND FingerID IN (1,2,3,4,5,6,7,8,9,10)) AS BT1 ON E.Ecode = BT1.Ecode 

		LEFT JOIN (SELECT DISTINCT Ecode FROM Biometric WHERE [Format] IN (203,206) AND FingerID IN (1,2,3,4)) AS BT2 ON E.Ecode = BT2.Ecode

		LEFT JOIN (SELECT DISTINCT Ecode FROM Biometric WHERE [Format] IN (203,206) AND FingerID IN (7,8,9,10)) AS BT3 ON E.Ecode = BT3.Ecode

		LEFT JOIN (SELECT DISTINCT Ecode FROM Biometric WHERE FingerID = 11) AS BT4 ON E.Ecode = BT4.Ecode

		LEFT JOIN (SELECT DISTINCT Ecode FROM Employee_Terminal_Authentication_Relation WHERE AuthenticationID IN(1,3,4,5,8,9,10) AND Status = 'Success') AS EREL ON E.Ecode = EREL.Ecode

WHERE   E.CorpEmpCode <> 'Admin' AND E.Role <> 'Visitor'