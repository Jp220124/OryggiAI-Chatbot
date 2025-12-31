# Oryggi Frontend API Reference

## Overview
This document captures all the frontend APIs used by the Oryggi Manager Web application. These APIs were captured using Playwright MCP by performing actual operations in the frontend.

**Base URL:** `https://localhost/OryggiWebServceCoreApi/OryggiWebApi/`

**Common Query Parameters:**
- `ClientVersion` - Client version string (e.g., "24.07.2025")
- `IPAddress` - Client IP address (e.g., "localhost")
- `OperatorEcode` - Operator employee code (e.g., 1 for Admin)

---

## 1. Employee Management APIs

### 1.1 Create/Update Employee
**Endpoint:** `POST /UpdateEmployeeWithLog`

**Query Parameters:**
- `IPAddress` - Client IP address
- `OperatorEcode` - Operator employee code
- `ClientVersion` - Client version

**Request Body:** Employee object with all details

**Used For:** Creating new employees and updating existing employee details

### 1.2 Get Employee Details
**Endpoint:** `GET /Get_Employee_Details_By_CorpEmpCode`

**Query Parameters:**
- `CorpEmpCode` - Employee corporate code (e.g., "TEST001")
- `ClientVersion` - Client version

**Response:** Complete employee details object

### 1.3 Get Employee Data (Bulk)
**Endpoint:** `POST /GetEmployeeDataAsync`

**Query Parameters:**
- `clientVersion` - Client version

**Request Body:** Filter criteria for employee list

**Used For:** Employee dashboard grid data

### 1.4 Get Ecode by Corp Emp Code
**Endpoint:** `GET /getEcodeByCorpEmpCode`

**Query Parameters:**
- `CorpEmpCode` - Corporate employee code

**Response:** Internal employee code (Ecode)

---

## 2. Visitor Management APIs

### 2.1 Register Visitor with Access Control
**Endpoint:** `POST /SaveVisitorDetailsWithAccessControl`

**Request Body:** Complete visitor object including:
```json
{
  "EmpName": "FirstName LastName",
  "CorpEmpCode": "PhoneNumber",
  "MobileNumner": "PhoneNumber",
  "IDType": "Aadhaar Card",
  "IDNumber": "123456789012",
  "PresentCardNo": "CardNumber",
  "WhomEmpCode": "HostEmployeeCode",
  "PurposeType": "Meeting",
  "Expected_IN_Time": "2025-11-27T12:35",
  "Expected_OUT_Time": "2025-11-27T20:35",
  "NumberOfVisitors": 1,
  "OperatorEcode": 1
}
```

**Used For:** Registering new visitors and pre-booked visitors

### 2.2 Search Visitors
**Endpoint:** `GET /GetSearchedVisitors`

**Query Parameters:**
- `SearchedValue` - Search term (phone number, name)
- `ClientVersion` - Client version

**Response:** List of matching visitors

### 2.3 Get Visitor Basic Details
**Endpoint:** `GET /GetVisitorBasicDetail`

**Query Parameters:**
- `SearchValue` - Phone number or visitor code
- `ClientVersion` - Client version

**Response:** Basic visitor information

### 2.4 Get Visitors Meeting List
**Endpoint:** `POST /GetVisitorsMeetingWithSelectedColumns`

**Query Parameters:**
- `StartDate` - Start date filter
- `EndDate` - End date filter
- `Columns` - Comma-separated column names
- `OperatorCorpEmpCode` - Operator code
- `ClientVersion` - Client version

**Used For:** Visitor dashboard grid data

### 2.5 Check Pre-Enrollment
**Endpoint:** `GET /IsPreEnrollmentExistForVisitorAndDate`

**Query Parameters:**
- `CorpEmpCode` - Visitor code/phone
- `ExpectedINTime` - Expected check-in time
- `ClientVersion` - Client version

---

## 3. Access Control APIs

### 3.1 Grant Terminal Access
**Endpoint:** `POST /AddAuthentication_Terminal`

**Query Parameters:**
- `IPAddress` - Client IP address
- `OperatorEcode` - Operator employee code

**Request Body:** Authentication configuration including:
- Employee Ecode
- Terminal ID
- Authentication Type (1001=Card, 2=Fingerprint, 3=Card+Finger, 5=Face)
- Schedule ID (63=All Access, 0=No Access)
- Start Date
- Expiry Date

**Used For:** Granting employee access to specific terminals/doors

### 3.2 Get Terminal Authentication List
**Endpoint:** `GET /GetTerminalAuthenticationListByEcode`

**Query Parameters:**
- `Ecode` - Employee internal code
- `ClientVersion` - Client version

**Response:** List of terminal access assignments for employee

### 3.3 Send TCP Command to Terminal
**Endpoint:** `GET /SendTCPCommand`

**Query Parameters:**
- `Command` - TCP command (e.g., "EATR,1")
- `host` - Terminal IP address
- `LogDetail` - Log description
- `Port` - TCP port (default: 13000)

**Used For:** Syncing access data to physical terminal devices

---

## 4. Card Management APIs

### 4.1 Add Card to Card Master
**Endpoint:** `POST /AddCardInCardMaster`

**Request Body:** Card details object

**Used For:** Registering new cards in the system

### 4.2 Check Duplicate Card
**Endpoint:** `GET /CheckDuplicateCardNo`

**Query Parameters:**
- `CardNo` - Card number to check
- `Ecode` - Employee code (to exclude)
- `ClientVersion` - Client version

**Response:** Boolean indicating if card is duplicate

### 4.3 Get Card Details by Ecode
**Endpoint:** `GET /getCardDetailsByEcode`

**Query Parameters:**
- `Ecode` - Employee internal code
- `ClientVersion` - Client version

**Response:** List of cards assigned to employee

### 4.4 Get Card Master Details
**Endpoint:** `GET /GetCardMasterDetails`

**Query Parameters:**
- `PageNumber` - Page number
- `PageSize` - Page size
- `CardNo` - Card number filter

**Response:** Paginated card details

---

## 5. Terminal/Door APIs

### 5.1 Get All Terminals
**Endpoint:** `GET /GetAllTerminal`

**Query Parameters:**
- `OperatorEcode` - Operator employee code
- `hardWareTypeID` - Hardware type filter (0=all)
- `ClientVersion` - Client version

**Response:** List of all terminals/doors

### 5.2 Get Terminal Groups
**Endpoint:** `GET /GetTerminalGroup`

**Query Parameters:**
- `ClientVersion` - Client version

**Response:** List of terminal groups/zones

### 5.3 Get Terminal IP List
**Endpoint:** `GET /getTerminalIPList`

**Query Parameters:**
- `ClientVersion` - Client version

**Response:** List of terminal IP addresses

---

## 6. Master Data APIs

### 6.1 Authentication Types
**Endpoint:** `GET /GetAuthenticationMaster`

**Response:**
| ID | Name |
|----|------|
| 1001 | Card |
| 2 | Fingerprint |
| 3 | Card + Finger |
| 5 | Face |

### 6.2 Access Schedules
**Endpoint:** `GET /GetAccessSchedule`

**Response:**
| ID | Name |
|----|------|
| 63 | All Access |
| 0 | No Access |
| ... | Custom schedules |

### 6.3 ID Types (for Visitors)
**Endpoint:** `GET /GetIDTypes`

**Response:** List of ID proof types (Aadhaar, PAN, Passport, DL, VoterID)

### 6.4 Purpose Types
**Endpoint:** `GET /GetPurposeTypes`

**Response:** List of visit purposes (Meeting, Interview, Delivery, etc.)

### 6.5 Departments
**Endpoint:** `GET /Get_DepartmentDetail_By_BranchCode`

**Query Parameters:**
- `BranchCode` - Branch code
- `ClientVersion` - Client version

### 6.6 Designations
**Endpoint:** `GET /Get_Designation_Detail`

**Query Parameters:**
- `ClientVersion` - Client version

### 6.7 Companies
**Endpoint:** `GET /Get_Company_Detail`

**Query Parameters:**
- `ClientVersion` - Client version

### 6.8 Branches
**Endpoint:** `GET /Get_BranchDetail_By_Ccode`

**Query Parameters:**
- `Ccode` - Company code
- `ClientVersion` - Client version

---

## 7. Biometric APIs

### 7.1 Get Finger Templates
**Endpoint:** `GET /GetFingerListByTemplate`

**Query Parameters:**
- `Ecode` - Employee internal code
- `TemplateType` - FINGER, FACE, or PALM
- `ClientVersion` - Client version

### 7.2 Get Template Image
**Endpoint:** `GET /GetTemplateImage`

**Query Parameters:**
- `Ecode` - Employee internal code

---

## 8. Frontend URL Patterns

### Employee Operations
- **Dashboard:** `/dashboards/employee-dashboard`
- **Create Employee:** `/dashboards/enroll-visitor?Operation=EnrollE`
- **Edit Employee:** `/dashboards/enroll-visitor?CorpEmpCode={code}&Operation=EditE`

### Visitor Operations
- **Dashboard:** `/dashboards/project-management`
- **Create Visitor:** `/dashboards/enroll-visitor?Operation=EnrollV`
- **Edit Visitor:** `/dashboards/enroll-visitor?CorpEmpCode={code}&Operation=EditV`

### Other
- **Terminals:** `/dashboards/terminals`
- **Reports:** `/dashboards/reports`

---

## 9. Workflow Summary

### Creating a New Employee
1. Navigate to Employee Dashboard
2. Click "Create Employee"
3. Fill employee details form
4. Add card number (Employee Card tab)
5. Select terminals and click "ADD TO TERMINAL" (Authentication tab)
6. Click Save
7. APIs called:
   - `POST /UpdateEmployeeWithLog`
   - `POST /AddCardInCardMaster`
   - `POST /AddAuthentication_Terminal`

### Registering a Visitor
1. Navigate to Visitors Dashboard
2. Click "Create New Visitor"
3. Enter phone number (search first)
4. Fill visitor details form
5. Assign visitor card
6. Click Register
7. API called: `POST /SaveVisitorDetailsWithAccessControl`

### Granting Door Access
1. Edit employee
2. Go to Authentication tab
3. Select terminal(s) from list
4. Choose Authentication Type and Schedule
5. Click "ADD TO TERMINAL"
6. Confirm dialog
7. API called: `POST /AddAuthentication_Terminal`

---

## 10. Implementation Notes for Chatbot

### Key Differences from Swagger
- Frontend uses `/OryggiWebApi/` namespace
- Most operations require `ClientVersion` parameter
- Employee and Visitor use same enrollment page with different `Operation` parameter
- Card enrollment happens as part of employee save, not separate API

### Required Parameters
- Always include `ClientVersion=24.07.2025` (or current version)
- Include `OperatorEcode` for audit trail
- Include `IPAddress` for logging

### Authentication Values
```python
AUTH_TYPES = {
    "card": 1001,
    "fingerprint": 2,
    "card_finger": 3,
    "face": 5
}

SCHEDULE_IDS = {
    "all_access": 63,
    "no_access": 0
}
```
