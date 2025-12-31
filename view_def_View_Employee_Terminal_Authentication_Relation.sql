-- View: View_Employee_Terminal_Authentication_Relation
-- ------------------------------------------------------------------------------

CREATE VIEW [dbo].[View_Employee_Terminal_Authentication_Relation]

AS

SELECT        dbo.EmployeeMaster.CorpEmpCode, dbo.EmployeeMaster.Ecode, dbo.MachineMaster.IPAddress, dbo.MachineMaster.DeviceType, dbo.MachineMaster.Location, dbo.MachineMaster.DomainName, 

                         dbo.AuthenticationMaster.AuthenticationName, dbo.Access_Schedules.Schedule_Name, dbo.Employee_Terminal_Authentication_Relation.WhiteList, dbo.Employee_Terminal_Authentication_Relation.VIP_list_flag, 

                         dbo.Employee_Terminal_Authentication_Relation.Expiry_date, dbo.Employee_Terminal_Authentication_Relation.DataLocation, dbo.Employee_Terminal_Authentication_Relation.Status, 

                         dbo.Employee_Terminal_Authentication_Relation.Error, dbo.EmployeeMaster.EmpName, dbo.EmployeeMaster.PresentCardNo, dbo.Employee_Terminal_Authentication_Relation.TerminalID, 

                         dbo.Employee_Terminal_Authentication_Relation.AuthenticationID, dbo.Employee_Terminal_Authentication_Relation.ScheduleID, dbo.EmployeeMaster.IsBlackListed, dbo.MachineMaster.ControllerID

FROM            dbo.Employee_Terminal_Authentication_Relation INNER JOIN

                         dbo.EmployeeMaster ON dbo.Employee_Terminal_Authentication_Relation.Ecode = dbo.EmployeeMaster.Ecode INNER JOIN

                         dbo.AuthenticationMaster ON dbo.Employee_Terminal_Authentication_Relation.AuthenticationID = dbo.AuthenticationMaster.AuthenticationID INNER JOIN

                         dbo.MachineMaster ON dbo.Employee_Terminal_Authentication_Relation.TerminalID = dbo.MachineMaster.TerminalID INNER JOIN

                         dbo.Access_Schedules ON dbo.Employee_Terminal_Authentication_Relation.ScheduleID = dbo.Access_Schedules.ScheduleID

WHERE        (dbo.MachineMaster.DeviceType NOT LIKE 'SEMAC%')