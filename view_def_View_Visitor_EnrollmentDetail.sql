-- View: View_Visitor_EnrollmentDetail
-- ------------------------------------------------------------------------------

CREATE VIEW [dbo].[View_Visitor_EnrollmentDetail]

AS

SELECT        M.Ecode, V.CorpEmpCode, V.FName, V.LName, M.Image, M.Whom_To_Visit, 

                         M.Expected_IN_Time, M.IN_Time, M.Expected_OUT_Time, M.OUT_Time, M.Purpose, M.ID_Proof_Type, 

                         M.ID_Proof_Detail, M.ID_Proof_Image, M.MobileNumner, M.OTP, M.Issued_Card_Number, M.Status, 

                         M.TermnalGroupID, M.Document_Detail, M.Vachel_Number, M.Create_Time, V.Role, 

                         E.CorpEmpCode AS WhomCorpEmpCode, dbo.PurposeMaster.PurposeType, V.EmpName, E.EmpName AS WhomEmpName, M.Filter, 

                         M.ID, V.PresentCardNo, E.ReportingHeadEcode, V.Address1, V.IsBlackListed, V.E_mail, 

                         E.E_mail AS EmpEmail, V.Sex, M.Document_File, M.Created_By, M.Remarks, M.NumberOfVisitors, 

                         M.VisitorType, IDProofMaster.IDProofType AS IDProofName, DeptMaster.Dname AS WhomDepartmentName, V.VehicleDetail, M.QRCodeValue, 

                         V.ServerSync, DeptMaster.Dcode, dbo.CompanyMaster.Ccode, dbo.BranchMaster.BranchCode, V.Catcode, V.SecCode, 

                         V.DesCode, V.Gcode, M.Field1, M.AreaGroupID, AreaGroupMaster.AreaGroupName

FROM            Vistor_Details M INNER JOIN

                         EmployeeMaster V ON M.Ecode = V.Ecode INNER JOIN

                         EmployeeMaster E ON M.Whom_To_Visit = E.Ecode INNER JOIN

                         SectionMaster ON E.SecCode = SectionMaster.SecCode INNER JOIN

                         DeptMaster ON SectionMaster.Dcode = DeptMaster.Dcode INNER JOIN

						 BranchMaster ON BranchMaster.BranchCode = DeptMaster.BranchCode INNER JOIN

						 CompanyMaster ON CompanyMaster.Ccode = BranchMaster.Ccode INNER JOIN

                         PurposeMaster ON M.Purpose = PurposeMaster.PurposeID LEFT JOIN

                         IDProofMaster ON M.ID_Proof_Type = IDProofMaster.IDProofID LEFT JOIN

						 AreaGroupMaster ON AreaGroupMaster.AreaGroupID = M.AreaGroupID