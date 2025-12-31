-- View: Vw_TerminalDetail_VMS
-- ------------------------------------------------------------------------------

CREATE VIEW [dbo].[Vw_TerminalDetail_VMS]

AS

SELECT        dbo.MachineMaster.MachineID, dbo.MachineMaster.DeviceType, dbo.MachineMaster.TerminalID, dbo.MachineMaster.IPAddress, dbo.MachineMaster.DomainName, dbo.MachineMaster.PortNo, dbo.MachineMaster.Location, 

                         dbo.MachineMaster.Connectiontype, dbo.MachineMaster.comboAppProtocol, dbo.MachineMaster.Sno, dbo.MachineMaster.LKey, dbo.MachineMaster.Connection_Status, dbo.MachineMaster.Configuration, 

                         dbo.MachineMaster.DataLocation, dbo.MachineMaster.MIFAREStartBlock, dbo.MachineMaster.MIFARENoofBlocks, dbo.MachineMaster.MIFAREKeyPolicy, dbo.MachineMaster.CheckExpiryDate, 

                         dbo.MachineMaster.EnableAccessSchedule, dbo.MachineMaster.EnableVIPAuthentication, dbo.MachineMaster.EnableWhiteList, dbo.MachineMaster.func_mode, dbo.MachineMaster.sdac_door_unlock_dur, 

                         dbo.MachineMaster.sdac_max_door_held_open_dur, dbo.MachineMaster.sdac_push_btn_mode, dbo.MachineMaster.sdac_rte_egress_timeout, dbo.MachineMaster.sdac_rte_mode, dbo.MachineMaster.tom_mode, 

                         dbo.MachineMaster.tom_duration, dbo.MachineMaster.audiovolume, dbo.MachineMaster.remote_msg_conffeedback_interface, dbo.MachineMaster.send_ethernet_state, dbo.MachineMaster.host_on_no_response, 

                         dbo.MachineMaster.remote_msg_ip_confhost_1_ip, dbo.MachineMaster.remote_msg_ip_confhost_1_port, dbo.MachineMaster.bio_security_settingsffd_security_level, 

                         dbo.MachineMaster.bio_security_settingsmatching_threshold, dbo.MachineMaster.enrollacquisition_threshold, dbo.MachineMaster.ControllerID, dbo.MachineMaster.DoorID, dbo.MachineMaster.sc_read_profile, 

                         dbo.MachineMaster.Dcode, dbo.MachineMaster.APIKey, dbo.WiegandMaster.ProxPortInputFormat, dbo.WiegandMaster.ExternalPortInputFormat, dbo.WiegandMaster.ExternalPortInputType, dbo.WiegandMaster.ReadProfile, 

                         dbo.WiegandMaster.EnrollUserID, dbo.WiegandMaster.ActivateWiegandOutput, dbo.WiegandMaster.VerificationPass, dbo.WiegandMaster.VerificationFail, dbo.WiegandMaster.IdentificationPass, 

                         dbo.WiegandMaster.IdentificationFail, dbo.WiegandMaster.Duress, dbo.WiegandMaster.Tamper, dbo.WiegandMaster.ExternalPortOutputType, dbo.WiegandMaster.SetPulseWidthTo, dbo.WiegandMaster.SetIntervalTo, 

                         dbo.WiegandMaster.InputDataLine, dbo.WiegandMaster.OutputDataLine, dbo.WiegandMaster.InputClockLine, dbo.WiegandMaster.OutputClockLine, dbo.MachineMaster.CardOnly, dbo.MachineMaster.FingerOnly, 

                         dbo.MachineMaster.CardAndFinger, dbo.MachineMaster.CardAndPin, dbo.MachineMaster.CardAndFingerAndPin, dbo.MachineMaster.UserWithoutMask, dbo.MachineMaster.ImageLog, 

                         dbo.MachineMaster.LOG_ACTION_USER_WITHOUT_MASK, dbo.MachineMaster.LOG_ACTION_REJECTED_BY_SCHEDULE, dbo.MachineMaster.LOG_ACTION_USER_RULE_CHECK_FAILURE, dbo.MachineMaster.ReadQRCode, 

                         dbo.MachineMaster.FirmwareVersion, dbo.MachineMaster.CameraCommand, dbo.MachineMaster.HardwareTypeID, dbo.MachineMaster.DataConnectionOutputTypeID, dbo.MachineMaster.IOModuleTypeID, cbdd.BranchCode, 

                         cbdd.Ccode, dcot.DataConnectionOutputTypeName, imt.IOModuleTypeName, dbo.MachineMaster.CameraIPAddress, dbo.MachineMaster.CameraUserName, dbo.MachineMaster.CameraPassword, 

                         dbo.MachineMaster.Update_Date

FROM            dbo.MachineMaster LEFT OUTER JOIN

                         dbo.DataConnectionOutputTypeMaster AS dcot ON dcot.ID = dbo.MachineMaster.DataConnectionOutputTypeID LEFT OUTER JOIN

                         dbo.Vw_CompanyBranchDepartmentDetail_VMS AS cbdd ON cbdd.Dcode = dbo.MachineMaster.Dcode LEFT OUTER JOIN

                         dbo.WiegandMaster ON dbo.MachineMaster.TerminalID = dbo.WiegandMaster.TerminalID LEFT OUTER JOIN

                         dbo.IOModuleTyp