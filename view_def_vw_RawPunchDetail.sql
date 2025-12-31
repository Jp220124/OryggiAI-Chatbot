-- View: vw_RawPunchDetail
-- ------------------------------------------------------------------------------



CREATE VIEW [dbo].[vw_RawPunchDetail]

AS

SELECT  TOP (100) PERCENT dbo.MachineRawPunch.CardNo, CONVERT(datetime, dbo.MachineRawPunch.PunchTime, 106) AS ATDate, dbo.MachineRawPunch.PunchTime, dbo.MachineRawPunch.IsManual, 

            dbo.MachineRawPunch.TransactionId, dbo.MachineRawPunch.InOut, dbo.MachineMaster.Location, dbo.EmployeeMaster.Image, dbo.MachineRawPunch.ECode, dbo.AllEmployeeUnion.CorpEmpCode, 

            dbo.AllEmployeeUnion.EmpName, dbo.AllEmployeeUnion.SecCode, dbo.SectionMaster.Dcode, dbo.DeptMaster.Dname, dbo.DeptMaster.BranchCode, dbo.BranchMaster.Ccode, dbo.AllEmployeeUnion.Gcode, 

            dbo.AllEmployeeUnion.Catcode, dbo.AllEmployeeUnion.DesCode, dbo.DesignationMaster.DesName, dbo.MachineRawPunch.MachineID, dbo.MachineMaster.TerminalID, dbo.MachineMaster.DomainName, 

            dbo.AllEmployeeUnion.Role, dbo.AllEmployeeUnion.StatusID, dbo.MachineRawPunch.nEventLogIdn, dbo.MachineRawPunch.Status, dbo.MachineMaster.IPAddress,

            (SELECT AuthenticationName FROM dbo.AuthenticationMaster WHERE AuthenticationID = dbo.MachineRawPunch.Channel) AS Authentication

FROM    dbo.BranchMaster INNER JOIN

            dbo.DeptMaster ON dbo.BranchMaster.BranchCode = dbo.DeptMaster.BranchCode INNER JOIN

            dbo.SectionMaster ON dbo.DeptMaster.Dcode = dbo.SectionMaster.Dcode INNER JOIN

            dbo.AllEmployeeUnion ON dbo.SectionMaster.SecCode = dbo.AllEmployeeUnion.SecCode INNER JOIN

            dbo.DesignationMaster ON dbo.AllEmployeeUnion.DesCode = dbo.DesignationMaster.DesCode INNER JOIN

            dbo.EmployeeMaster ON dbo.AllEmployeeUnion.Ecode = dbo.EmployeeMaster.Ecode RIGHT OUTER JOIN

            dbo.MachineRawPunch INNER JOIN

            dbo.MachineMaster ON dbo.MachineRawPunch.MachineID = dbo.MachineMaster.MachineID ON dbo.AllEmployeeUnion.Ecode = dbo.MachineRawPunch.ECode

ORDER BY dbo.MachineRawPunch.PunchTime