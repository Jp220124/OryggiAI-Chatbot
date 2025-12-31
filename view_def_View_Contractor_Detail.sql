-- View: View_Contractor_Detail
-- ------------------------------------------------------------------------------



Create VIEW [dbo].[View_Contractor_Detail]

AS

SELECT        dbo.ContractorMaster.ContractorID, dbo.ContractorMaster.Contractor_Code, dbo.ContractorMaster.Name, dbo.ContractorMaster.Address, dbo.ContractorMaster.Email, dbo.ContractorMaster.Mobile, 

                         dbo.ContractorMaster.Description, dbo.Contractor_Detail.Client_ID, dbo.Contractor_Detail.PO_Number, dbo.Contractor_Detail.PO_Date, dbo.Contractor_Detail.Job_Detail, dbo.Contractor_Detail.Servce_Start_Date, 

                         dbo.Contractor_Detail.Max_Labour_Limt, dbo.Contractor_Detail.Status, dbo.Contractor_Detail.Remark, dbo.Contractor_Detail.CreatedDate, dbo.Contractor_Detail.LastModifiedDate, dbo.Contractor_Detail.Servce_End_Date

FROM            dbo.ContractorMaster INNER JOIN

                         dbo.Contractor_Detail ON dbo.ContractorMaster.ContractorID = dbo.Contractor_Detail.ContractorID