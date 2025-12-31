-- View: AllEmployeeUnion
-- ------------------------------------------------------------------------------

CREATE VIEW [dbo].[AllEmployeeUnion]

AS

SELECT        [Ecode], [CorpEmpCode], [Active], [Gcode], [Catcode], [DesCode], [SecCode], [EmpName], [GuardianName], [DateofBirth], [DateofJoin], [PresentCardNo], [Sex], [IsMarried], [Qualification], [Experience], [Address1], [Telephone1], 

                         [E_mail], [Address2], [Telephone2], [BloodGroup], [LeavingDate], [LeavingReason], [Password], [Role], [DefaultPolicy], [PermissableLateArrival], [PermissbleeEarlyDeparture], [MinWorkHourForPresent], [IsHalfDayAllowed], 

                         [MinWorkHourForHalfDay], [IsShortDayAllowed], [MinWorkHourForShortDay], [OvertimeAllowed], [MinDurationReqForOvertime], [OnePunchPresentMarking], [FWOAssigned], [FirstWO], [SWOAssigned], [SWO], [SWOFirst], 

                         [SWOSecond], [SWOThird], [SWOFourth], [SWOFifth], [SWOType], [WorkMinuteFomula], [ESINo], [IsBlackListed], [ReportingHeadEcode], [FP1_ID], [FP2_ID], [DFP_ID], [FName], [LName], [IsEnrolled], [WiegandValue], 

                         [LoginAuthenticationID], [LastUpdate], [UserID], [Password2], [queryString], [guid], [userDefined1], [IN_Out_Status], [ContractorID], [Latitude], [Longitude], [formatID], [facilityCode], [ContarctManualEndDate], [PO_Number], 

                         [ServerSync], [emptype], [Created_Date], [VehicleDetail], [StatusID], [2DStatus]

FROM            EmployeeMaster

UNION

SELECT        [Ecode], [CorpEmpCode], [Active], [Gcode], [Catcode], [DesCode], [SecCode], [EmpName], [GuardianName], [DateofBirth], [DateofJoin], [PresentCardNo], [Sex], [IsMarried], [Qualification], [Experience], [Address1], [Telephone1], 

                         [E_mail], [Address2], [Telephone2], [BloodGroup], [LeavingDate], [LeavingReason], [Password], [Role], [DefaultPolicy], [PermissableLateArrival], [PermissbleeEarlyDeparture], [MinWorkHourForPresent], [IsHalfDayAllowed], 

                         [MinWorkHourForHalfDay], [IsShortDayAllowed], [MinWorkHourForShortDay], [OvertimeAllowed], [MinDurationReqForOvertime], [OnePunchPresentMarking], [FWOAssigned], [FirstWO], [SWOAssigned], [SWO], [SWOFirst], 

                         [SWOSecond], [SWOThird], [SWOFourth], [SWOFifth], [SWOType], [WorkMinuteFomula], [ESINo], [IsBlackListed], [ReportingHeadEcode], [FP1_ID], [FP2_ID], [DFP_ID], [FName], [LName], [IsEnrolled], [WiegandValue], 

                         [LoginAuthenticationID], [LastUpdate], [UserID], [Password2], [queryString], [guid], [userDefined1], [IN_Out_Status], [ContractorID], [Latitude], [Longitude], [formatID], [facilityCode], [ContarctManualEndDate], [PO_Number], 

                         [ServerSync], [emptype], [Created_Date], [VehicleDetail], [StatusID], [2DStatus]

FROM            EmployeeMaster_Deleted