-- View: vw_VisitorBasicDetail
-- ------------------------------------------------------------------------------



---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------



CREATE VIEW [dbo].[vw_VisitorBasicDetail]

AS

SELECT        TOP (100) PERCENT dbo.Vistor_Details.ID, dbo.EmployeeMaster.Ecode, dbo.EmployeeMaster.CorpEmpCode, dbo.EmployeeMaster.FName, dbo.EmployeeMaster.LName, dbo.EmployeeMaster.Sex, 

                         dbo.EmployeeMaster.Address1, dbo.EmployeeMaster.E_mail, dbo.EmployeeMaster.Image, dbo.EmployeeMaster.IsBlackListed, dbo.EmployeeMaster.Telephone1, dbo.Vistor_Details.Expected_IN_Time, 

                         dbo.Vistor_Details.ID_Proof_Type, dbo.Vistor_Details.ID_Proof_Detail, dbo.Vistor_Details.ID_Proof_Image, dbo.EmployeeMaster.VehicleDetail, dbo.Vistor_Details.QRCodeValue

FROM            dbo.EmployeeMaster INNER JOIN

                         dbo.Vistor_Details ON dbo.EmployeeMaster.Ecode = dbo.Vistor_Details.Ecode

WHERE        (dbo.EmployeeMaster.Role = 'Visitor')