"""
LangGraph Action Orchestrator with Human-in-the-Loop
Handles destructive actions that require user confirmation before execution
"""

from typing import Any, Dict, List, Optional, TypedDict, Annotated, Literal
from langgraph.graph import StateGraph, END
from langgraph.types import interrupt, Command
from langgraph.checkpoint.memory import MemorySaver
import operator
from loguru import logger
import google.generativeai as genai
import json
import re

from app.config import settings
from app.tools.access_control_tools import (
    grant_access_tool,
    block_access_tool,
    revoke_access_tool,
    list_user_access_tool
)
from app.tools.access_control_tools_extended import (
    visitor_registration_tool,
    temporary_card_tool,
    database_backup_tool,
    card_enrollment_tool,
    employee_enrollment_tool,
    door_access_tool,
    authentication_management_tool,
    biometric_enrollment_tool
)
# Phase 7 - Employee Action Tool (Activate/Deactivate via Gateway Agent)
from app.tools.employee_action_tool import employee_action_tool
# Phase 8 - Employee Blacklist Tool (Blacklist/Remove from Blacklist via Gateway Agent)
from app.tools.employee_blacklist_tool import employee_blacklist_tool
# Phase 9 - Employee Terminate Tool (Terminate/Un-terminate via Gateway Agent)
from app.tools.employee_terminate_tool import employee_terminate_tool
from app.services.pending_actions_store import (
    pending_actions_store,
    PendingAction,
    ActionStatus
)
from app.middleware.audit_logger import audit_logger
# Use Gateway-based employee lookup (routes through WebSocket to local DB)
# This replaces direct pyodbc connection that times out from VM
from app.services.gateway_employee_lookup import gateway_employee_lookup_service as employee_lookup_service


class ActionState(TypedDict):
    """
    State for LangGraph action workflow with Human-in-the-Loop

    Tracks the action request, confirmation status, and execution results
    """
    # Input
    question: str
    user_id: str
    user_role: str
    session_id: str

    # Action classification
    action_type: Optional[str]  # grant_access, block_access, revoke_access, list_access
    action_params: Optional[Dict[str, Any]]
    requires_confirmation: bool

    # Pending action tracking
    pending_action_id: Optional[str]
    confirmation_message: Optional[str]

    # User response (after interrupt)
    user_confirmed: Optional[bool]
    user_rejection_reason: Optional[str]

    # Execution tracking
    tools_called: Annotated[List[str], operator.add]
    action_result: Optional[Dict[str, Any]]

    # Output
    answer: str
    success: bool
    error: Optional[str]
    awaiting_confirmation: bool


class ActionOrchestrator:
    """
    LangGraph-based action orchestrator with Human-in-the-Loop

    Workflow:
    1. Classify Action -> Determine what access control action user wants
    2. Check Confirmation -> Determine if action requires user confirmation
    3. Request Confirmation -> If destructive, pause for user approval (interrupt)
    4. Execute Action -> After approval, execute the action
    5. Format Response -> Return result to user

    The interrupt pattern allows the workflow to pause at step 3, wait for
    user confirmation, and then resume at step 4.

    Examples:
        - "List access for user EMP001" -> list_access (no confirmation)
        - "Grant user EMP001 access to Server Room" -> grant_access (requires confirmation)
        - "Block user EMP002 from Building A" -> block_access (requires confirmation)
    """

    # Mapping of action types to tools
    ACTION_TOOLS = {
        # Phase 5 - Original Access Control Tools
        "grant_access": grant_access_tool,
        "block_access": block_access_tool,
        "revoke_access": revoke_access_tool,
        "list_access": list_user_access_tool,
        # Phase 6 - Extended Access Control Tools
        "register_visitor": visitor_registration_tool,
        "assign_temporary_card": temporary_card_tool,
        "database_backup": database_backup_tool,
        "enroll_card": card_enrollment_tool,
        "enroll_employee": employee_enrollment_tool,
        "manage_door_access": door_access_tool,
        "manage_authentication": authentication_management_tool,
        "trigger_biometric_enrollment": biometric_enrollment_tool,
        # Phase 7 - Employee Action Tool (Activate/Deactivate via Gateway Agent)
        "employee_action": employee_action_tool,
        # Phase 8 - Employee Blacklist Tool (Blacklist/Remove from Blacklist via Gateway Agent)
        "employee_blacklist": employee_blacklist_tool,
        # Phase 9 - Employee Terminate Tool (Terminate/Un-terminate via Gateway Agent)
        "employee_terminate": employee_terminate_tool
    }

    # Actions that require confirmation (destructive)
    DESTRUCTIVE_ACTIONS = {
        # Phase 5
        "grant_access", "block_access", "revoke_access",
        # Phase 6
        "register_visitor", "assign_temporary_card", "database_backup",
        "enroll_card", "enroll_employee", "manage_door_access", "manage_authentication",
        "trigger_biometric_enrollment",
        # Phase 7 - Employee Action (Activate/Deactivate)
        "employee_action",
        # Phase 8 - Employee Blacklist (Blacklist/Remove from Blacklist)
        "employee_blacklist",
        # Phase 9 - Employee Terminate (Terminate/Un-terminate)
        "employee_terminate"
    }

    def __init__(self):
        """Initialize orchestrator with Gemini for action classification"""
        genai.configure(api_key=settings.gemini_api_key)
        self.model = genai.GenerativeModel(settings.gemini_model)

        # Memory checkpointer for interrupt/resume support
        self.checkpointer = MemorySaver()

        # Build LangGraph state machine
        self.workflow = self._build_workflow()

    def _build_workflow(self) -> StateGraph:
        """
        Build LangGraph state machine for action orchestration with interrupt

        Workflow Graph:
            START
              |
        classify_action
              |
        check_requires_confirmation
              |
        +-----+-----+
        |           |
        |     request_confirmation (interrupt)
        |           |
        +-----+-----+
              |
        execute_action
              |
        format_response
              |
            END
        """
        workflow = StateGraph(ActionState)

        # Add nodes
        workflow.add_node("classify_action", self._classify_action)
        workflow.add_node("check_requires_confirmation", self._check_requires_confirmation)
        workflow.add_node("request_confirmation", self._request_confirmation)
        workflow.add_node("execute_action", self._execute_action)
        workflow.add_node("format_response", self._format_response)

        # Define edges
        workflow.set_entry_point("classify_action")

        # After classification, check if confirmation needed
        workflow.add_edge("classify_action", "check_requires_confirmation")

        # Route based on confirmation requirement
        workflow.add_conditional_edges(
            "check_requires_confirmation",
            self._route_after_confirmation_check,
            {
                "needs_confirmation": "request_confirmation",
                "no_confirmation": "execute_action",
                "invalid_action": "format_response"
            }
        )

        # After confirmation request (which uses interrupt), execute
        workflow.add_edge("request_confirmation", "execute_action")

        # After execution, format response
        workflow.add_edge("execute_action", "format_response")
        workflow.add_edge("format_response", END)

        return workflow.compile(checkpointer=self.checkpointer)

    def _classify_action(self, state: ActionState) -> ActionState:
        """
        Step 1: Classify the action request using Gemini

        Extracts:
        - action_type: grant_access, block_access, revoke_access, list_access
        - action_params: Parameters needed for the action
        """
        logger.info(f"[ACTION_ORCHESTRATOR] Classifying action for: {state['question']}")

        try:
            prompt = f"""Analyze this user request and extract the access control action.

USER REQUEST:
{state['question']}

ACTION TYPES:
1. "grant_access" - User wants to give someone access to a location/system
2. "block_access" - User wants to block someone's access to a SPECIFIC area/door (NOT blacklist - use employee_blacklist for complete system ban)
3. "revoke_access" - User wants to remove a specific permission
4. "list_access" - User wants to view someone's current access permissions
5. "register_visitor" - User wants to register a visitor (requires: first_name, last_name, mobile, whom_to_visit, purpose, id_proof_type, id_proof_detail)
6. "assign_temporary_card" - User wants to assign a temporary card to visitor/contractor
7. "database_backup" - User wants to backup the access control database
8. "enroll_card" - User wants to enroll/assign a card to an employee with door access
9. "enroll_employee" - User wants to add a new employee to the access control system
10. "manage_door_access" - User wants to grant or block access to specific doors
11. "manage_authentication" - User wants to add or remove authentication methods (card, fingerprint, face) for an employee
12. "trigger_biometric_enrollment" - User wants to trigger biometric enrollment mode on a device for an employee (face, palm, finger)
13. "employee_action" - User wants to ACTIVATE or DEACTIVATE an employee (enable/disable their biometric access completely)
14. "employee_blacklist" - User wants to BLACKLIST or REMOVE FROM BLACKLIST an employee. Keywords: "blacklist", "add to blacklist", "remove from blacklist", "unblacklist". NOTE: This is DIFFERENT from block_access - blacklist completely bans an employee from ALL Oryggi systems, while block_access only blocks specific areas/doors.
15. "employee_terminate" - User wants to TERMINATE or UN-TERMINATE (reinstate) an employee (termination permanently disables access, marks employee as resigned/left)
16. "none" - Request is not related to access control

CRITICAL: target_user_id EXTRACTION RULES:
- target_user_id is the PERSON being affected (granted/blocked/revoked)
- It can be: employee code (like "28734", "EMP001"), employee name (like "cv", "john", "John Smith"), or card number
- When user says "user X", "employee X", "for X", "to X" - extract X as target_user_id
- IGNORE words like "user", "employee", "access" - extract the ACTUAL identifier after them
- If user says "block access to user cv" -> target_user_id = "cv" (NOT "user")
- If user says "grant access to employee 28734" -> target_user_id = "28734"
- If user says "block cv" -> target_user_id = "cv"

PARAMETERS TO EXTRACT:
For grant_access:
- target_user_id: The employee identifier (name, code, or card) - REQUIRED
- target_type: Type of access (door, zone, terminal, building) - optional
- target_id: ID of the target (e.g., "DOOR-45") - optional
- target_name: Human-readable location name (e.g., "Server Room") - optional
- start_date: Start date (ISO format or null for now)
- end_date: End date (ISO format or null for 1 year)

For block_access:
- target_user_id: User identifier to block - REQUIRED
- target_type: Type of access to block - optional
- target_id: ID of the target - optional
- target_name: Name of the target - optional
- reason: Reason for blocking - optional

For revoke_access:
- target_user_id: User identifier whose permission to revoke - REQUIRED
- permission_id: Permission ID to revoke - optional
- reason: Reason for revocation - optional

For list_access:
- target_user_id: User identifier to list permissions for - REQUIRED
- include_inactive: Whether to include revoked/expired (default: false)

For register_visitor:
- first_name: Visitor's first name - REQUIRED (extract from visitor name)
- last_name: Visitor's last name - optional (extract from visitor name if provided)
- mobile_number: Mobile phone number - optional
- whom_to_visit: Employee name/code being visited - optional
- purpose: Purpose of visit (Meeting, Interview, etc.) - optional
- id_proof_type: Type of ID (Aadhaar, PAN, Passport, DL, VoterID, Other) - REQUIRED
- id_proof_detail: ID proof number - REQUIRED
- email: Visitor email - optional
- company: Visitor company - optional

For assign_temporary_card:
- target_user_id: Visitor/employee ID - REQUIRED
- card_number: Card number to assign - REQUIRED
- expiry_datetime: When card expires (ISO format) - REQUIRED

For database_backup:
- database_name: Database name (default: Oryggi)
- backup_type: full/differential/log (default: full)

For enroll_card:
- employee_id: Employee identifier - REQUIRED
- card_number: Card number - REQUIRED
- access_scope: card_only (just assign card), all_doors, or specific_doors (default: card_only)
- door_ids: List of door IDs for specific_doors
- door_names: List of door names for specific_doors

For enroll_employee:
- corp_emp_code: Employee code - REQUIRED
- emp_name: Full name - REQUIRED
- department_code: Department - optional
- email: Email - optional
- card_number: Card to assign - optional

For manage_door_access:
- employee_id: Employee identifier - REQUIRED
- action: grant or block - REQUIRED
- door_ids: List of door IDs - REQUIRED (one of door_ids or door_names)
- door_names: List of door names - REQUIRED (one of door_ids or door_names)

For manage_authentication:
- employee_id: Employee identifier (code or name) - REQUIRED
- action: add or remove - REQUIRED
- authentication_type: Auth type (1001=card, 2=fingerprint, 5=face, 3=card+fingerprint, 6=card+face) - default 1001

For trigger_biometric_enrollment:
- employee_id: Employee identifier (code or name) - REQUIRED
- biometric_type: Type of biometric (face, palm, finger, all) - default "face"
- terminal_name: Name of the terminal/device to use - optional
- timeout_seconds: Enrollment timeout in seconds - optional (default: 60)

For employee_action:
- action: "activate" or "deactivate" - REQUIRED
- ecode: Employee ECode (ID number in Oryggi system) - REQUIRED
- employee_name: Employee name (optional, for display)
- reason: Reason for the action (optional)

For employee_blacklist:
- action: "blacklist" or "remove_blacklist" (also accept "unblacklist") - REQUIRED
- ecode: Employee ECode (ID number in Oryggi system) - REQUIRED
- employee_name: Employee name (optional, for display)
- reason: Reason for blacklisting (required for blacklist, optional for remove)

For employee_terminate:
- action: "terminate" or "un_terminate" (also accept "reinstate", "unterminate") - REQUIRED
- ecode: Employee ECode (ID number in Oryggi system) - REQUIRED
- employee_name: Employee name (optional, for display)
- reason: Reason for termination (required for terminate, optional for un_terminate)
- leaving_date: Date of leaving (optional, defaults to today for terminate)

Return ONLY a JSON object with this exact structure:
{{
  "action_type": "grant_access|block_access|revoke_access|list_access|register_visitor|assign_temporary_card|database_backup|enroll_card|enroll_employee|manage_door_access|manage_authentication|trigger_biometric_enrollment|employee_action|employee_blacklist|employee_terminate|none",
  "action_params": {{...parameters...}},
  "confidence": 0.0-1.0
}}

EXAMPLES:
Request: "Block access to user cv"
Response: {{"action_type": "block_access", "action_params": {{"target_user_id": "cv"}}, "confidence": 0.95}}

Request: "grant access to cv"
Response: {{"action_type": "grant_access", "action_params": {{"target_user_id": "cv"}}, "confidence": 0.95}}

Request: "Give employee EMP001 access to the Server Room door"
Response: {{"action_type": "grant_access", "action_params": {{"target_user_id": "EMP001", "target_type": "door", "target_name": "Server Room"}}, "confidence": 0.9}}

Request: "Block John's access to Building A immediately"
Response: {{"action_type": "block_access", "action_params": {{"target_user_id": "John", "target_type": "building", "target_name": "Building A", "reason": "Immediate block requested"}}, "confidence": 0.85}}

Request: "What access does EMP002 have?"
Response: {{"action_type": "list_access", "action_params": {{"target_user_id": "EMP002", "include_inactive": false}}, "confidence": 0.95}}

Request: "How many employees are there?"
Response: {{"action_type": "none", "action_params": {{}}, "confidence": 0.99}}

Request: "Register visitor John Smith with Aadhaar ID 1234567890"
Response: {{"action_type": "register_visitor", "action_params": {{"first_name": "John", "last_name": "Smith", "id_proof_type": "Aadhaar", "id_proof_detail": "1234567890"}}, "confidence": 0.95}}

Request: "Register a visitor named Test User with passport number AB123456"
Response: {{"action_type": "register_visitor", "action_params": {{"first_name": "Test", "last_name": "User", "id_proof_type": "Passport", "id_proof_detail": "AB123456"}}, "confidence": 0.95}}

Request: "Backup the database"
Response: {{"action_type": "database_backup", "action_params": {{"database_name": "Oryggi", "backup_type": "full"}}, "confidence": 0.95}}

Request: "Assign card 12345 to visitor V001 for 2 days"
Response: {{"action_type": "assign_temporary_card", "action_params": {{"target_user_id": "V001", "card_number": "12345"}}, "confidence": 0.9}}

Request: "Enroll new employee John Doe with code EMP999 in IT department"
Response: {{"action_type": "enroll_employee", "action_params": {{"corp_emp_code": "EMP999", "emp_name": "John Doe", "department_code": "IT"}}, "confidence": 0.95}}

Request: "Enroll card 12345678 for employee EMP001"
Response: {{"action_type": "enroll_card", "action_params": {{"employee_id": "EMP001", "card_number": "12345678", "access_scope": "card_only"}}, "confidence": 0.95}}

Request: "Assign card 99991111 to TERMTEST2191"
Response: {{"action_type": "enroll_card", "action_params": {{"employee_id": "TERMTEST2191", "card_number": "99991111", "access_scope": "card_only"}}, "confidence": 0.95}}

Request: "Give employee EMP001 card 12345 with access to Server Room"
Response: {{"action_type": "enroll_card", "action_params": {{"employee_id": "EMP001", "card_number": "12345", "access_scope": "specific_doors", "door_names": ["Server Room"]}}, "confidence": 0.9}}

Request: "Enroll face biometric for employee EMP001"
Response: {{"action_type": "trigger_biometric_enrollment", "action_params": {{"employee_id": "EMP001", "biometric_type": "face"}}, "confidence": 0.95}}

Request: "Start palm enrollment for John on terminal Palm-01"
Response: {{"action_type": "trigger_biometric_enrollment", "action_params": {{"employee_id": "John", "biometric_type": "palm", "terminal_name": "Palm-01"}}, "confidence": 0.9}}

Request: "Trigger fingerprint enrollment for 28734"
Response: {{"action_type": "trigger_biometric_enrollment", "action_params": {{"employee_id": "28734", "biometric_type": "finger"}}, "confidence": 0.95}}

Request: "Deactivate employee with ECode 1001"
Response: {{"action_type": "employee_action", "action_params": {{"action": "deactivate", "ecode": 1001}}, "confidence": 0.95}}

Request: "Activate employee 28734"
Response: {{"action_type": "employee_action", "action_params": {{"action": "activate", "ecode": 28734}}, "confidence": 0.95}}

Request: "Disable employee John Smith"
Response: {{"action_type": "employee_action", "action_params": {{"action": "deactivate", "employee_name": "John Smith"}}, "confidence": 0.9}}

Request: "Enable employee access for ECode 5555"
Response: {{"action_type": "employee_action", "action_params": {{"action": "activate", "ecode": 5555}}, "confidence": 0.95}}

Request: "Blacklist employee 2374 for policy violation"
Response: {{"action_type": "employee_blacklist", "action_params": {{"action": "blacklist", "ecode": 2374, "reason": "policy violation"}}, "confidence": 0.95}}

Request: "blacklist employee 10001"
Response: {{"action_type": "employee_blacklist", "action_params": {{"action": "blacklist", "ecode": 10001}}, "confidence": 0.95}}

Request: "Add employee 1001 to blacklist"
Response: {{"action_type": "employee_blacklist", "action_params": {{"action": "blacklist", "ecode": 1001}}, "confidence": 0.95}}

Request: "Remove employee 2374 from blacklist"
Response: {{"action_type": "employee_blacklist", "action_params": {{"action": "remove_blacklist", "ecode": 2374}}, "confidence": 0.95}}

Request: "Unblacklist employee John Smith"
Response: {{"action_type": "employee_blacklist", "action_params": {{"action": "remove_blacklist", "employee_name": "John Smith"}}, "confidence": 0.9}}

Request: "Terminate employee 2374 due to resignation"
Response: {{"action_type": "employee_terminate", "action_params": {{"action": "terminate", "ecode": 2374, "reason": "resignation"}}, "confidence": 0.95}}

Request: "Employee 1001 has resigned, please terminate"
Response: {{"action_type": "employee_terminate", "action_params": {{"action": "terminate", "ecode": 1001, "reason": "resigned"}}, "confidence": 0.95}}

Request: "Un-terminate employee 2374"
Response: {{"action_type": "employee_terminate", "action_params": {{"action": "un_terminate", "ecode": 2374}}, "confidence": 0.95}}

Request: "Reinstate employee John Smith"
Response: {{"action_type": "employee_terminate", "action_params": {{"action": "un_terminate", "employee_name": "John Smith"}}, "confidence": 0.9}}

Now classify this request:
{state['question']}

JSON Response:"""

            response = self.model.generate_content(prompt)
            classification = response.text.strip()

            # Parse JSON response
            if "```json" in classification:
                classification = classification.split("```json")[1].split("```")[0].strip()
            elif "```" in classification:
                classification = classification.split("```")[1].split("```")[0].strip()

            result = json.loads(classification)

            state["action_type"] = result.get("action_type")
            state["action_params"] = result.get("action_params", {})

            logger.info(
                f"[ACTION_ORCHESTRATOR] Action classified: {state['action_type']}, "
                f"params={list(state['action_params'].keys())}"
            )

            return state

        except Exception as e:
            logger.error(f"[ACTION_ORCHESTRATOR] Action classification failed: {str(e)}")
            # Use fallback keyword-based classification
            result = self._classify_action_fallback(state['question'])
            state["action_type"] = result.get("action_type")
            state["action_params"] = result.get("action_params", {})
            return state

    def _classify_action_fallback(self, question: str) -> Dict[str, Any]:
        """Fallback keyword-based action classifier"""
        question_lower = question.lower()
        target_user_id = None

        # Try multiple patterns to extract target user
        # Pattern 1: "employee EMP999" or "to employee EMP999" - employee code pattern
        emp_code_match = re.search(r'employee\s+([A-Za-z]{2,4}\d{2,})', question, re.IGNORECASE)
        if emp_code_match:
            target_user_id = emp_code_match.group(1).upper()

        # Pattern 2: "emp XXX" or "user XXX" (as standalone words, not part of "employee")
        if not target_user_id:
            user_id_match = re.search(r'\b(?:emp|user)\b\s*[-_]?\s*(\d+|[a-z]+\d+)', question_lower)
            if user_id_match:
                target_user_id = user_id_match.group(1).upper()

        # Pattern 3: "to XXX" or "for XXX" - extract what comes after (but not "to employee")
        if not target_user_id:
            # Match "grant access to ADITYA SINGH" or "block access for 2424130187"
            to_match = re.search(r'(?:to|for)\s+(?!employee\b)([a-zA-Z0-9\s]+?)(?:\s+access|\s+from|\s*$)', question, re.IGNORECASE)
            if to_match:
                target_user_id = to_match.group(1).strip()

        # Pattern 4: Just a number (employee code) anywhere in the string
        if not target_user_id:
            number_match = re.search(r'\b(\d{3,})\b', question)  # 3+ digit numbers are likely employee codes
            if number_match:
                target_user_id = number_match.group(1)

        # Pattern 5: Employee code pattern anywhere (EMP001, EMP999, etc.)
        if not target_user_id:
            code_match = re.search(r'\b([A-Za-z]{2,4}\d{3,})\b', question)
            if code_match:
                target_user_id = code_match.group(1).upper()

        # Pattern 6: Name at the end - "grant access ADITYA SINGH" or "block ADITYA SINGH"
        if not target_user_id:
            # Match capitalized words at end that look like names
            name_match = re.search(r'(?:grant|block|revoke|list)\s+(?:access\s+)?(?:to\s+)?([A-Z][a-zA-Z]*(?:\s+[A-Z][a-zA-Z]*)*)\s*$', question)
            if name_match:
                target_user_id = name_match.group(1).strip()

        logger.info(f"[ACTION_ORCHESTRATOR] Fallback extracted target_user_id: {target_user_id}")

        if any(kw in question_lower for kw in ['grant', 'give', 'allow', 'provide access']):
            return {
                "action_type": "grant_access",
                "action_params": {"target_user_id": target_user_id}
            }
        elif any(kw in question_lower for kw in ['block', 'deny', 'stop', 'prevent']):
            return {
                "action_type": "block_access",
                "action_params": {"target_user_id": target_user_id}
            }
        elif any(kw in question_lower for kw in ['revoke', 'remove', 'delete permission']):
            return {
                "action_type": "revoke_access",
                "action_params": {"target_user_id": target_user_id}
            }
        elif any(kw in question_lower for kw in ['list', 'show', 'what access', 'permissions']):
            return {
                "action_type": "list_access",
                "action_params": {"target_user_id": target_user_id}
            }

        # Phase 6 - Extended Access Control Actions Fallback
        elif any(kw in question_lower for kw in ['enroll employee', 'add employee', 'new employee', 'create employee', 'register employee']):
            # Try to extract employee details
            emp_name = None
            corp_emp_code = None

            # Try to extract name after "enroll employee" or "add employee"
            # Stop at keywords like "with", "code", "in", "to", "for"
            name_match = re.search(r'(?:enroll|add|new|create|register)\s+(?:a\s+)?(?:new\s+)?employee\s+(?:named?\s+)?([A-Za-z]+(?:\s+[A-Za-z]+)?)(?:\s+(?:with|code|in|to|for|department)|$)', question, re.IGNORECASE)
            if name_match:
                emp_name = name_match.group(1).strip()

            # Try to extract employee code (pattern like EMP001, EMP999, etc.)
            code_match = re.search(r'(?:code|with code|employee code|emp code)?\s*([A-Z]{2,4}[-_]?\d{3,})', question, re.IGNORECASE)
            if code_match:
                corp_emp_code = code_match.group(1).upper()
            else:
                # Try just a code pattern
                code_match = re.search(r'\b([A-Z]{2,4}\d{3,})\b', question, re.IGNORECASE)
                if code_match:
                    corp_emp_code = code_match.group(1).upper()

            logger.info(f"[ACTION_ORCHESTRATOR] Fallback enroll_employee: name={emp_name}, code={corp_emp_code}")
            return {
                "action_type": "enroll_employee",
                "action_params": {
                    "emp_name": emp_name,
                    "corp_emp_code": corp_emp_code
                }
            }

        elif any(kw in question_lower for kw in ['enroll card', 'assign card', 'issue card', 'card enrollment']):
            # Try to extract card number and employee ID
            card_number = None
            employee_id = target_user_id

            # Try to extract card number
            card_match = re.search(r'card\s*(?:number|no|#)?\s*[:=]?\s*(\d{6,})', question, re.IGNORECASE)
            if card_match:
                card_number = card_match.group(1)
            else:
                # Look for long number (card numbers are usually 8+ digits)
                card_match = re.search(r'\b(\d{8,})\b', question)
                if card_match:
                    card_number = card_match.group(1)

            logger.info(f"[ACTION_ORCHESTRATOR] Fallback enroll_card: employee={employee_id}, card={card_number}")
            return {
                "action_type": "enroll_card",
                "action_params": {
                    "employee_id": employee_id,
                    "card_number": card_number,
                    "access_scope": "card_only"
                }
            }

        elif any(kw in question_lower for kw in ['register visitor', 'add visitor', 'new visitor', 'visitor registration', 'create visitor']):
            # Try to extract visitor name
            first_name = None
            last_name = None

            name_match = re.search(r'(?:visitor|register)\s+(?:named?\s+)?([A-Za-z]+)(?:\s+([A-Za-z]+))?', question, re.IGNORECASE)
            if name_match:
                first_name = name_match.group(1)
                last_name = name_match.group(2) if name_match.group(2) else None

            logger.info(f"[ACTION_ORCHESTRATOR] Fallback register_visitor: first_name={first_name}, last_name={last_name}")
            return {
                "action_type": "register_visitor",
                "action_params": {
                    "first_name": first_name,
                    "last_name": last_name
                }
            }

        elif any(kw in question_lower for kw in ['temporary card', 'temp card', 'visitor card']):
            return {
                "action_type": "assign_temporary_card",
                "action_params": {"target_user_id": target_user_id}
            }

        elif any(kw in question_lower for kw in ['database backup', 'backup database', 'db backup', 'backup oryggi', 'backup the database']):
            return {
                "action_type": "database_backup",
                "action_params": {"database_name": "Oryggi", "backup_type": "full"}
            }

        elif any(kw in question_lower for kw in ['door access', 'manage door', 'grant door', 'block door']):
            # Determine if grant or block
            action = "grant" if "grant" in question_lower else "block"
            return {
                "action_type": "manage_door_access",
                "action_params": {
                    "employee_id": target_user_id,
                    "action": action
                }
            }

        # IMPORTANT: Check biometric enrollment BEFORE manage_authentication
        # because auth keywords like 'palm', 'face', 'finger' overlap
        elif any(kw in question_lower for kw in ['enroll biometric', 'biometric enrollment', 'trigger enrollment',
                                                   'enroll face', 'enroll palm', 'enroll finger', 'enroll fingerprint',
                                                   'start enrollment', 'begin enrollment', 'capture biometric',
                                                   'face enrollment', 'palm enrollment', 'finger enrollment',
                                                   'fingerprint enrollment', 'biometric capture']):
            # Determine biometric type
            biometric_type = "face"  # default
            if any(kw in question_lower for kw in ['palm']):
                biometric_type = "palm"
            elif any(kw in question_lower for kw in ['finger', 'fingerprint']):
                biometric_type = "finger"
            elif any(kw in question_lower for kw in ['all biometric', 'all biometrics']):
                biometric_type = "all"

            # Try to extract terminal name
            terminal_name = None
            terminal_match = re.search(r'(?:on|at|terminal|device)\s+([A-Za-z0-9_-]+)', question, re.IGNORECASE)
            if terminal_match:
                terminal_name = terminal_match.group(1)

            logger.info(f"[ACTION_ORCHESTRATOR] Fallback biometric_enrollment: employee={target_user_id}, type={biometric_type}, terminal={terminal_name}")
            return {
                "action_type": "trigger_biometric_enrollment",
                "action_params": {
                    "employee_id": target_user_id,
                    "biometric_type": biometric_type,
                    "terminal_name": terminal_name
                }
            }

        elif any(kw in question_lower for kw in ['add authentication', 'remove authentication', 'add fingerprint', 'remove fingerprint',
                                                   'add face', 'remove face', 'add card auth', 'remove card auth',
                                                   'manage authentication', 'authentication type', 'set authentication',
                                                   'enable fingerprint', 'disable fingerprint', 'enable face', 'disable face',
                                                   'fusion', 'palm', 'card only', 'face only', 'finger only']):
            # Determine action (add or remove)
            action = "remove" if any(kw in question_lower for kw in ['remove', 'disable', 'delete']) else "add"

            # Determine authentication type - prefer named types over numeric codes
            auth_type = None
            auth_type_name = None

            # Check for authentication type names (more user-friendly)
            # These map to API's authentication type names
            auth_type_mappings = {
                # Name-based mappings (priority)
                'fusion': 'Fusion',
                'palm': 'Palm',
                'palm only': 'Palm Only',
                'face only': 'Face Only',
                'finger only': 'Finger Only',
                'fingerprint only': 'Finger Only',
                'card only': 'Card Only',
                'card + face': 'Card + Face',
                'card+face': 'Card + Face',
                'card and face': 'Card + Face',
                'card + finger': 'Card + Finger',
                'card+finger': 'Card + Finger',
                'card and finger': 'Card + Finger',
                'card + fingerprint': 'Card + Finger',
                'card+fingerprint': 'Card + Finger',
                'card and fingerprint': 'Card + Finger',
                'card + palm': 'Card + Palm',
                'card+palm': 'Card + Palm',
                'card and palm': 'Card + Palm',
            }

            # Try to find authentication type name from keywords
            for keyword, type_name in auth_type_mappings.items():
                if keyword in question_lower:
                    auth_type_name = type_name
                    logger.info(f"[ACTION_ORCHESTRATOR] Fallback found auth_type_name: {auth_type_name} from keyword: {keyword}")
                    break

            # If no name found, fall back to numeric detection
            if not auth_type_name:
                if any(kw in question_lower for kw in ['fingerprint', 'finger']):
                    auth_type = 2
                elif any(kw in question_lower for kw in ['face', 'facial']):
                    auth_type = 5
                elif any(kw in question_lower for kw in ['card']):
                    auth_type = 1001
                else:
                    # Default to Card Only if nothing specified
                    auth_type = 1001

            logger.info(f"[ACTION_ORCHESTRATOR] Fallback manage_authentication: employee={target_user_id}, action={action}, auth_type_name={auth_type_name}, auth_type={auth_type}")

            # Build params - prefer auth_type_name if available
            params = {
                "employee_id": target_user_id,
                "action": action,
            }
            if auth_type_name:
                params["authentication_type_name"] = auth_type_name
            else:
                params["authentication_type"] = auth_type

            return {
                "action_type": "manage_authentication",
                "action_params": params
            }

        # Phase 7 - Employee Action (Activate/Deactivate)
        elif any(kw in question_lower for kw in ['activate employee', 'deactivate employee', 'enable employee', 'disable employee',
                                                   'activate user', 'deactivate user', 'activate ecode', 'deactivate ecode']):
            # Determine action
            action = "activate" if any(kw in question_lower for kw in ['activate', 'enable']) else "deactivate"

            # Try to extract ecode (numeric employee ID)
            ecode = None
            ecode_match = re.search(r'(?:ecode|employee|user)\s*[:=]?\s*(\d+)', question, re.IGNORECASE)
            if ecode_match:
                ecode = int(ecode_match.group(1))
            else:
                # Try to find any number that looks like an ecode
                number_match = re.search(r'\b(\d{3,})\b', question)
                if number_match:
                    ecode = int(number_match.group(1))

            # Try to extract employee name if no ecode
            employee_name = None
            if not ecode:
                name_match = re.search(r'(?:employee|user)\s+([A-Za-z]+(?:\s+[A-Za-z]+)?)', question, re.IGNORECASE)
                if name_match:
                    employee_name = name_match.group(1).strip()

            logger.info(f"[ACTION_ORCHESTRATOR] Fallback employee_action: action={action}, ecode={ecode}, name={employee_name}")
            return {
                "action_type": "employee_action",
                "action_params": {
                    "action": action,
                    "ecode": ecode,
                    "employee_name": employee_name
                }
            }

        # Phase 8 - Employee Blacklist (Blacklist/Remove from Blacklist)
        elif any(kw in question_lower for kw in ['blacklist employee', 'blacklist user', 'add to blacklist', 'remove from blacklist',
                                                   'unblacklist employee', 'unblacklist user', 'remove blacklist']):
            # Determine action
            if any(kw in question_lower for kw in ['remove from blacklist', 'unblacklist', 'remove blacklist']):
                action = "remove_blacklist"
            else:
                action = "blacklist"

            # Try to extract ecode (numeric employee ID)
            ecode = None
            ecode_match = re.search(r'(?:ecode|employee|user)\s*[:=]?\s*(\d+)', question, re.IGNORECASE)
            if ecode_match:
                ecode = int(ecode_match.group(1))
            else:
                # Try to find any number that looks like an ecode
                number_match = re.search(r'\b(\d{3,})\b', question)
                if number_match:
                    ecode = int(number_match.group(1))

            # Try to extract employee name if no ecode
            employee_name = None
            if not ecode:
                name_match = re.search(r'(?:employee|user)\s+([A-Za-z]+(?:\s+[A-Za-z]+)?)', question, re.IGNORECASE)
                if name_match:
                    employee_name = name_match.group(1).strip()

            # Try to extract reason for blacklisting
            reason = None
            reason_match = re.search(r'(?:for|reason|because)\s+(.+?)(?:\.|$)', question, re.IGNORECASE)
            if reason_match:
                reason = reason_match.group(1).strip()

            logger.info(f"[ACTION_ORCHESTRATOR] Fallback employee_blacklist: action={action}, ecode={ecode}, name={employee_name}, reason={reason}")
            return {
                "action_type": "employee_blacklist",
                "action_params": {
                    "action": action,
                    "ecode": ecode,
                    "employee_name": employee_name,
                    "reason": reason
                }
            }

        # Phase 9 - Employee Terminate (Terminate/Un-terminate)
        elif any(kw in question_lower for kw in ['terminate employee', 'terminate user', 'un-terminate employee', 'unterminate employee',
                                                   'reinstate employee', 'un terminate', 'has resigned', 'has left']):
            # Determine action
            if any(kw in question_lower for kw in ['un-terminate', 'unterminate', 'un terminate', 'reinstate']):
                action = "un_terminate"
            else:
                action = "terminate"

            # Try to extract ecode (numeric employee ID)
            ecode = None
            ecode_match = re.search(r'(?:ecode|employee|user)\s*[:=]?\s*(\d+)', question, re.IGNORECASE)
            if ecode_match:
                ecode = int(ecode_match.group(1))
            else:
                # Try to find any number that looks like an ecode
                number_match = re.search(r'\b(\d{3,})\b', question)
                if number_match:
                    ecode = int(number_match.group(1))

            # Try to extract employee name if no ecode
            employee_name = None
            if not ecode:
                name_match = re.search(r'(?:employee|user)\s+([A-Za-z]+(?:\s+[A-Za-z]+)?)', question, re.IGNORECASE)
                if name_match:
                    employee_name = name_match.group(1).strip()

            # Try to extract reason for termination
            reason = None
            reason_match = re.search(r'(?:for|reason|because|due to)\s+(.+?)(?:\.|$)', question, re.IGNORECASE)
            if reason_match:
                reason = reason_match.group(1).strip()
            elif 'resign' in question_lower:
                reason = "Resignation"

            logger.info(f"[ACTION_ORCHESTRATOR] Fallback employee_terminate: action={action}, ecode={ecode}, name={employee_name}, reason={reason}")
            return {
                "action_type": "employee_terminate",
                "action_params": {
                    "action": action,
                    "ecode": ecode,
                    "employee_name": employee_name,
                    "reason": reason
                }
            }

        return {"action_type": "none", "action_params": {}}

    def _check_requires_confirmation(self, state: ActionState) -> ActionState:
        """
        Step 2: Check if the action requires user confirmation

        Destructive actions (grant, block, revoke) require confirmation.
        Read-only actions (list) do not.
        """
        action_type = state.get("action_type")

        if action_type in self.DESTRUCTIVE_ACTIONS:
            state["requires_confirmation"] = True
            logger.info(f"[ACTION_ORCHESTRATOR] Action {action_type} requires confirmation")
        else:
            state["requires_confirmation"] = False
            logger.info(f"[ACTION_ORCHESTRATOR] Action {action_type} does not require confirmation")

        return state

    def _route_after_confirmation_check(self, state: ActionState) -> str:
        """Routing logic after confirmation check"""
        action_type = state.get("action_type")

        if action_type == "none" or action_type is None:
            logger.info("[ACTION_ORCHESTRATOR:ROUTE] Invalid action, routing to format_response")
            return "invalid_action"

        if state.get("requires_confirmation"):
            logger.info("[ACTION_ORCHESTRATOR:ROUTE] Needs confirmation, routing to request_confirmation")
            return "needs_confirmation"
        else:
            logger.info("[ACTION_ORCHESTRATOR:ROUTE] No confirmation needed, routing to execute_action")
            return "no_confirmation"

    def _request_confirmation(self, state: ActionState) -> ActionState:
        """
        Step 3: Request user confirmation using LangGraph interrupt

        This node:
        1. Creates a pending action record
        2. Generates confirmation message
        3. Uses interrupt() to pause workflow
        4. Workflow resumes when user confirms/rejects
        """
        logger.info("[ACTION_ORCHESTRATOR] Requesting user confirmation")

        action_type = state["action_type"]
        action_params = state["action_params"]
        tool = self.ACTION_TOOLS.get(action_type)

        if not tool:
            state["error"] = f"Unknown action type: {action_type}"
            state["success"] = False
            return state

        # Generate confirmation message
        confirmation_message = tool.get_confirmation_message(**action_params)
        state["confirmation_message"] = confirmation_message

        # Log the action request
        audit_logger.log_action_request(
            user_id=state["user_id"],
            user_role=state["user_role"],
            action_type=action_type,
            pending_action_id="pending",
            confirmation_message=confirmation_message,
            target_user_id=action_params.get("target_user_id"),
            target_type=action_params.get("target_type"),
            target_id=action_params.get("target_id"),
            target_name=action_params.get("target_name")
        )

        # Set flag for frontend
        state["awaiting_confirmation"] = True
        state["answer"] = confirmation_message

        logger.info(f"[ACTION_ORCHESTRATOR] Interrupting workflow for confirmation")

        # INTERRUPT: Pause workflow and wait for user response
        # When resumed, the Command will update the state with user's decision
        user_response = interrupt({
            "action_type": action_type,
            "action_params": action_params,
            "confirmation_message": confirmation_message,
            "session_id": state["session_id"]
        })

        # After resume, process user response
        if isinstance(user_response, dict):
            state["user_confirmed"] = user_response.get("confirmed", False)
            state["user_rejection_reason"] = user_response.get("reason")
            logger.info(f"[ACTION_ORCHESTRATOR] User response: confirmed={state['user_confirmed']}")
        else:
            # Direct boolean response
            state["user_confirmed"] = bool(user_response)

        # Log confirmation decision
        audit_logger.log_action_confirmation(
            user_id=state["user_id"],
            user_role=state["user_role"],
            pending_action_id=state.get("pending_action_id", "unknown"),
            approved=state["user_confirmed"],
            resolution_note=state.get("user_rejection_reason")
        )

        state["awaiting_confirmation"] = False

        return state

    async def _execute_action(self, state: ActionState) -> ActionState:
        """
        Step 4: Execute the action (after confirmation if required)
        """
        action_type = state.get("action_type")
        action_params = state.get("action_params", {})

        logger.info(f"[ACTION_ORCHESTRATOR] Executing action: {action_type}")

        # Check if user rejected (for destructive actions)
        if state.get("requires_confirmation") and not state.get("user_confirmed"):
            logger.info("[ACTION_ORCHESTRATOR] User rejected action")
            state["success"] = False
            state["error"] = "Action cancelled by user"
            state["answer"] = f"Action cancelled. {state.get('user_rejection_reason', '')}"
            return state

        # Get the tool
        tool = self.ACTION_TOOLS.get(action_type)
        if not tool:
            state["success"] = False
            state["error"] = f"Unknown action: {action_type}"
            return state

        try:
            # Prepare parameters
            params = {
                **action_params,
                "user_id": state["user_id"],
                "user_role": state["user_role"],
                "granted_by": state["user_id"],
                "blocked_by": state["user_id"],
                "revoked_by": state["user_id"]
            }

            # Execute tool
            result = await tool.run(user_role=state["user_role"], **params)

            state["action_result"] = result
            state["tools_called"] = [action_type]
            state["success"] = result.get("success", False)

            if not result.get("success"):
                state["error"] = result.get("error")

            logger.info(f"[ACTION_ORCHESTRATOR] Action executed: success={state['success']}")

            return state

        except Exception as e:
            logger.error(f"[ACTION_ORCHESTRATOR] Action execution failed: {str(e)}")
            state["success"] = False
            state["error"] = str(e)
            state["action_result"] = {"success": False, "error": str(e)}
            return state

    def _format_response(self, state: ActionState) -> ActionState:
        """
        Step 5: Format the final response
        """
        logger.info("[ACTION_ORCHESTRATOR] Formatting response")

        action_type = state.get("action_type")
        action_result = state.get("action_result", {})

        # Check for invalid action
        if action_type == "none" or action_type is None:
            state["answer"] = "I couldn't understand the access control action you requested. Please try rephrasing your request."
            state["success"] = False
            return state

        # Check for cancelled action
        if state.get("error") == "Action cancelled by user":
            return state

        # Format based on action type
        if action_result.get("success"):
            result_data = action_result.get("result", {})

            if action_type == "list_access":
                # Format permission list
                permissions = result_data.get("permissions", [])
                if permissions:
                    perm_lines = []
                    for p in permissions:
                        perm_lines.append(
                            f"- {p['target_name']} ({p['access_type']}): {p['status']} "
                            f"(expires: {p.get('expires_at', 'never')})"
                        )
                    state["answer"] = (
                        f"Access permissions for {result_data.get('user_id', 'user')}:\n\n" +
                        "\n".join(perm_lines)
                    )
                else:
                    state["answer"] = f"No active permissions found for user {action_result.get('user_id', 'specified')}."

            elif action_type == "grant_access":
                state["answer"] = (
                    f"Access granted successfully.\n\n"
                    f"- User: {action_result.get('result', {}).get('details', {}).get('user_id', 'N/A')}\n"
                    f"- Target: {action_result.get('result', {}).get('details', {}).get('target_name', 'N/A')}\n"
                    f"- Permission ID: {action_result.get('result', {}).get('permission_id', 'N/A')}"
                )

            elif action_type == "block_access":
                state["answer"] = (
                    f"Access blocked successfully.\n\n"
                    f"- User: {action_result.get('result', {}).get('details', {}).get('user_id', 'N/A')}\n"
                    f"- Target: {action_result.get('result', {}).get('details', {}).get('target_name', 'N/A')}\n"
                    f"- Reason: {action_result.get('result', {}).get('details', {}).get('reason', 'N/A')}"
                )

            elif action_type == "revoke_access":
                state["answer"] = (
                    f"Permission revoked successfully.\n\n"
                    f"- Permission ID: {action_result.get('result', {}).get('permission_id', 'N/A')}"
                )

        else:
            # Error response
            error_msg = state.get("error") or action_result.get("error", "Unknown error")
            state["answer"] = f"Action failed: {error_msg}"

        return state

    async def process(
        self,
        question: str,
        user_id: str,
        user_role: str,
        session_id: str,
        thread_id: Optional[str] = None,
        pending_action_id: Optional[str] = None,
        is_confirmation: bool = False,
        database_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process an action request (simplified approach - no LangGraph interrupt)

        Args:
            question: User's request
            user_id: User ID
            user_role: User's role
            session_id: Session ID
            thread_id: LangGraph thread ID for resumption
            pending_action_id: ID of pending action if this is a confirmation
            is_confirmation: True if user is confirming/rejecting a pending action
            database_id: User's database_id for correct gateway routing

        Returns:
            Dict with answer, success status, and any pending confirmation
        """
        logger.info(f"[ACTION_ORCHESTRATOR] Processing: {question} (database_id={database_id})")

        # Handle confirmation of pending action
        if pending_action_id:
            return await self._handle_pending_action_confirmation(
                pending_action_id=pending_action_id,
                is_confirmation=is_confirmation,
                user_id=user_id,
                user_role=user_role,
                session_id=session_id,
                database_id=database_id
            )

        try:
            # Step 1: Classify the action
            classification = await self._classify_action_simple(question)
            action_type = classification.get("action_type")
            action_params = classification.get("action_params", {})

            logger.info(f"[ACTION_ORCHESTRATOR] Classified: {action_type}")

            # Step 2: Enrich action params with employee lookup (for access control actions)
            # Actions that require a target employee
            EMPLOYEE_REQUIRED_ACTIONS = {"grant_access", "block_access", "revoke_access", "list_access", "enroll_card", "manage_door_access"}

            if action_type in self.DESTRUCTIVE_ACTIONS:
                target_user_id = action_params.get("target_user_id")

                # Check if target_user_id is required but missing
                if action_type in EMPLOYEE_REQUIRED_ACTIONS and not target_user_id:
                    logger.warning(f"[ACTION_ORCHESTRATOR] Missing target_user_id for action: {action_type}")
                    return {
                        "answer": f"I need to know which employee you want to {action_type.replace('_', ' ')}. Please specify the employee name, code, or card number.\n\nExample: '{action_type.replace('_', ' ')} to John Smith' or '{action_type.replace('_', ' ')} to employee 28734'",
                        "success": False,
                        "action_type": action_type,
                        "awaiting_confirmation": False,
                        "error": "Missing employee identifier"
                    }

                if target_user_id:
                    logger.info(f"[ACTION_ORCHESTRATOR] Looking up employee: {target_user_id}")
                    employee = await employee_lookup_service.get_employee_by_identifier(target_user_id)

                    if employee:
                        # Enrich action_params with employee details
                        action_params["employee_name"] = employee.name
                        action_params["employee_code"] = employee.corp_emp_code
                        action_params["employee_department"] = employee.department
                        action_params["employee_designation"] = employee.designation
                        action_params["employee_card_no"] = employee.card_no
                        action_params["employee_ecode"] = employee.ecode
                        # Update target_user_id to the actual employee code
                        action_params["target_user_id"] = employee.corp_emp_code
                        logger.info(f"[ACTION_ORCHESTRATOR] Employee found: {employee.name} ({employee.corp_emp_code})")
                    else:
                        # Employee not found - return error
                        logger.warning(f"[ACTION_ORCHESTRATOR] Employee not found: {target_user_id}")
                        return {
                            "answer": f"Could not find employee with identifier '{target_user_id}'. Please verify the employee code, name, or card number and try again.",
                            "success": False,
                            "action_type": action_type,
                            "awaiting_confirmation": False,
                            "error": f"Employee not found: {target_user_id}"
                        }

            # Step 2b: Special handling for employee_action - look up employee to get ecode
            if action_type == "employee_action":
                # Get the identifier from action_params (could be ecode or employee_name)
                ecode = action_params.get("ecode")
                employee_name = action_params.get("employee_name")

                # If we have employee_name but no ecode, look up the employee
                if employee_name and not ecode:
                    logger.info(f"[ACTION_ORCHESTRATOR] Looking up employee by name: {employee_name}")
                    employee = await employee_lookup_service.get_employee_by_identifier(employee_name)
                    if employee:
                        action_params["ecode"] = employee.ecode
                        action_params["employee_name"] = employee.name
                        action_params["employee_code"] = employee.corp_emp_code
                        action_params["employee_department"] = employee.department
                        action_params["employee_designation"] = employee.designation
                        action_params["employee_card_no"] = employee.card_no
                        logger.info(f"[ACTION_ORCHESTRATOR] Employee found: {employee.name} (ECode: {employee.ecode})")
                    else:
                        logger.warning(f"[ACTION_ORCHESTRATOR] Employee not found: {employee_name}")
                        return {
                            "answer": f"Could not find employee '{employee_name}'. Please verify the employee name or provide the ECode number.",
                            "success": False,
                            "action_type": action_type,
                            "awaiting_confirmation": False,
                            "error": f"Employee not found: {employee_name}"
                        }

                # If we have ecode, optionally look up employee details for display
                elif ecode and not employee_name:
                    logger.info(f"[ACTION_ORCHESTRATOR] Looking up employee by ecode: {ecode}")
                    employee = await employee_lookup_service.get_employee_by_identifier(str(ecode))
                    if employee:
                        action_params["employee_name"] = employee.name
                        action_params["employee_code"] = employee.corp_emp_code
                        action_params["employee_department"] = employee.department
                        action_params["employee_designation"] = employee.designation
                        action_params["employee_card_no"] = employee.card_no
                        logger.info(f"[ACTION_ORCHESTRATOR] Employee found: {employee.name} (ECode: {employee.ecode})")

                # Validate ecode is present
                if not action_params.get("ecode"):
                    return {
                        "answer": "I need the employee's ECode (ID number) to activate or deactivate them. Please provide the ECode.\n\nExample: 'deactivate employee 1001' or 'activate employee with ECode 28734'",
                        "success": False,
                        "action_type": action_type,
                        "awaiting_confirmation": False,
                        "error": "Missing employee ECode"
                    }

            # Step 3: Check if this is a valid action
            if action_type == "none" or action_type is None:
                return {
                    "answer": "I couldn't understand the access control action you requested. Please try rephrasing.",
                    "success": False,
                    "action_type": None,
                    "awaiting_confirmation": False
                }

            # Step 3: Check if action requires confirmation
            if action_type in self.DESTRUCTIVE_ACTIONS:
                # Get confirmation message from tool
                tool = self.ACTION_TOOLS.get(action_type)
                if tool:
                    confirmation_message = tool.get_confirmation_message(**action_params)
                else:
                    confirmation_message = f"Please confirm you want to execute: {action_type}"

                # Create pending action in store (so we can retrieve it on confirmation)
                pending_action = await pending_actions_store.create_pending_action(
                    session_id=session_id,
                    user_id=user_id,
                    user_role=user_role,
                    action_type=action_type,
                    tool_name=action_type,
                    action_params=action_params,
                    confirmation_message=confirmation_message,
                    langgraph_thread_id=thread_id or session_id,
                    expiration_minutes=5  # 5 minutes to confirm
                )

                logger.info(f"[ACTION_ORCHESTRATOR] Created pending action: {pending_action.id}")

                # Log the action request
                audit_logger.log_action_request(
                    user_id=user_id,
                    user_role=user_role,
                    action_type=action_type,
                    pending_action_id=pending_action.id,
                    confirmation_message=confirmation_message,
                    target_user_id=action_params.get("target_user_id"),
                    target_type=action_params.get("target_type"),
                    target_id=action_params.get("target_id"),
                    target_name=action_params.get("target_name")
                )

                logger.info(f"[ACTION_ORCHESTRATOR] Action requires confirmation")

                # Return early - frontend will show confirmation UI
                return {
                    "answer": confirmation_message,
                    "success": True,
                    "action_type": action_type,
                    "action_params": action_params,
                    "awaiting_confirmation": True,
                    "confirmation_message": confirmation_message,
                    "thread_id": thread_id or session_id,
                    "pending_action_id": pending_action.id,
                    "tools_called": []
                }

            # Step 4: For non-destructive actions (list_access), execute immediately
            logger.info(f"[ACTION_ORCHESTRATOR] Executing non-destructive action: {action_type}")
            result = await self._execute_action_direct(
                action_type=action_type,
                action_params=action_params,
                user_id=user_id,
                user_role=user_role
            )

            return {
                "answer": result.get("answer", ""),
                "success": result.get("success", True),
                "error": result.get("error"),
                "action_type": action_type,
                "action_result": result.get("action_result"),
                "awaiting_confirmation": False,
                "tools_called": [action_type],
                "thread_id": thread_id or session_id
            }

        except Exception as e:
            logger.error(f"[ACTION_ORCHESTRATOR] Process failed: {str(e)}", exc_info=True)
            return {
                "answer": f"Error processing action: {str(e)}",
                "success": False,
                "error": str(e),
                "tools_called": [],
                "awaiting_confirmation": False
            }

    async def _classify_action_simple(self, question: str) -> Dict[str, Any]:
        """Classify action using Gemini (simplified without state)"""
        try:
            prompt = f"""Analyze this user request and extract the access control action.

USER REQUEST:
{question}

ACTION TYPES:
1. "grant_access" - User wants to give someone access to a location/system
2. "block_access" - User wants to block someone's access to a SPECIFIC area/door (NOT blacklist - use employee_blacklist for complete system ban)
3. "revoke_access" - User wants to remove a specific permission
4. "list_access" - User wants to view someone's current access permissions
5. "register_visitor" - User wants to register a visitor (requires: first_name, last_name, mobile_number, whom_to_visit, purpose, id_proof_type, id_proof_detail)
6. "assign_temporary_card" - User wants to assign a temporary card to visitor/contractor (requires: target_user_id, card_number, expiry_datetime)
7. "database_backup" - User wants to backup the access control database
8. "enroll_card" - User wants to enroll/assign a card to an employee with door access (requires: employee_id, card_number, access_scope)
9. "enroll_employee" - User wants to add a new employee to the access control system (requires: corp_emp_code, emp_name)
10. "manage_door_access" - User wants to grant or block access to specific doors (requires: employee_id, action, door_ids or door_names)
11. "manage_authentication" - User wants to add or remove authentication methods (card, fingerprint, face) for an employee (requires: employee_id, action, authentication_type)
12. "trigger_biometric_enrollment" - User wants to trigger biometric enrollment mode on a device for an employee (face, palm, finger)
13. "employee_action" - User wants to ACTIVATE or DEACTIVATE an employee (enable/disable their biometric access completely). Parameters: action (activate/deactivate), ecode (employee ID number), employee_name (optional)
14. "employee_blacklist" - User wants to BLACKLIST or REMOVE FROM BLACKLIST an employee. Keywords: "blacklist", "add to blacklist", "remove from blacklist", "unblacklist". This completely bans employee from ALL systems. Parameters: action (blacklist/remove_blacklist), ecode, employee_name, reason
15. "employee_terminate" - User wants to TERMINATE or UN-TERMINATE (reinstate) an employee. Keywords: "terminate", "un-terminate", "reinstate", "resigned". Parameters: action (terminate/un_terminate), ecode, employee_name, reason, leaving_date
16. "none" - Request is not related to access control

CRITICAL: target_user_id EXTRACTION RULES:
- target_user_id is the PERSON being affected (granted/blocked/revoked)
- It can be: employee code (like "28734", "EMP001"), employee name (like "cv", "john", "John Smith"), or card number
- When user says "user X", "employee X", "for X", "to X" - extract X as target_user_id
- IGNORE words like "user", "employee", "access" - extract the ACTUAL identifier after them
- If user says "block access to user cv" -> target_user_id = "cv" (NOT "user")
- If user says "grant access to employee 28734" -> target_user_id = "28734"
- If user says "block cv" -> target_user_id = "cv"

PARAMETERS TO EXTRACT:
For grant_access:
- target_user_id: The employee identifier (name, code, or card) - REQUIRED
- target_type: Type of access (door, zone, terminal, building) - optional
- target_id: ID of the target (e.g., "DOOR-45") - optional
- target_name: Human-readable location name (e.g., "Server Room") - optional

For block_access:
- target_user_id: User identifier to block - REQUIRED
- target_type: Type of access to block - optional
- target_id: ID of the target - optional
- target_name: Name of the target - optional
- reason: Reason for blocking - optional

For revoke_access:
- target_user_id: User identifier whose permission to revoke - REQUIRED
- permission_id: Permission ID to revoke - optional
- reason: Reason for revocation - optional

For list_access:
- target_user_id: User identifier to list permissions for - REQUIRED
- include_inactive: Whether to include revoked/expired (default: false)

EXAMPLES:
"Block access to user cv" -> {{"action_type": "block_access", "action_params": {{"target_user_id": "cv"}}}}
"block user cv" -> {{"action_type": "block_access", "action_params": {{"target_user_id": "cv"}}}}
"Block access for employee 28734" -> {{"action_type": "block_access", "action_params": {{"target_user_id": "28734"}}}}
"grant access to cv" -> {{"action_type": "grant_access", "action_params": {{"target_user_id": "cv"}}}}
"Grant user 28734 access to Server Room" -> {{"action_type": "grant_access", "action_params": {{"target_user_id": "28734", "target_name": "Server Room"}}}}
"revoke john's access" -> {{"action_type": "revoke_access", "action_params": {{"target_user_id": "john"}}}}
"list access for EMP001" -> {{"action_type": "list_access", "action_params": {{"target_user_id": "EMP001"}}}}
"enroll face for EMP001" -> {{"action_type": "trigger_biometric_enrollment", "action_params": {{"employee_id": "EMP001", "biometric_type": "face"}}}}
"start palm enrollment for John" -> {{"action_type": "trigger_biometric_enrollment", "action_params": {{"employee_id": "John", "biometric_type": "palm"}}}}
"trigger fingerprint enrollment for 28734" -> {{"action_type": "trigger_biometric_enrollment", "action_params": {{"employee_id": "28734", "biometric_type": "finger"}}}}
"deactivate employee 1001" -> {{"action_type": "employee_action", "action_params": {{"action": "deactivate", "ecode": 1001}}}}
"activate employee with ECode 28734" -> {{"action_type": "employee_action", "action_params": {{"action": "activate", "ecode": 28734}}}}
"disable employee John Smith" -> {{"action_type": "employee_action", "action_params": {{"action": "deactivate", "employee_name": "John Smith"}}}}
"blacklist employee 10001" -> {{"action_type": "employee_blacklist", "action_params": {{"action": "blacklist", "ecode": 10001}}}}
"blacklist employee 2374 for policy violation" -> {{"action_type": "employee_blacklist", "action_params": {{"action": "blacklist", "ecode": 2374, "reason": "policy violation"}}}}
"add employee 1001 to blacklist" -> {{"action_type": "employee_blacklist", "action_params": {{"action": "blacklist", "ecode": 1001}}}}
"remove employee 2374 from blacklist" -> {{"action_type": "employee_blacklist", "action_params": {{"action": "remove_blacklist", "ecode": 2374}}}}
"unblacklist employee John" -> {{"action_type": "employee_blacklist", "action_params": {{"action": "remove_blacklist", "employee_name": "John"}}}}
"terminate employee 2374" -> {{"action_type": "employee_terminate", "action_params": {{"action": "terminate", "ecode": 2374}}}}
"employee 1001 has resigned" -> {{"action_type": "employee_terminate", "action_params": {{"action": "terminate", "ecode": 1001, "reason": "resigned"}}}}
"reinstate employee John" -> {{"action_type": "employee_terminate", "action_params": {{"action": "un_terminate", "employee_name": "John"}}}}

Return ONLY a JSON object:
{{"action_type": "...", "action_params": {{...}}}}

JSON Response:"""

            response = self.model.generate_content(prompt)
            classification = response.text.strip()

            logger.info(f"[ACTION_ORCHESTRATOR] Raw Gemini response: {classification[:500]}")

            # Parse JSON response
            if "```json" in classification:
                classification = classification.split("```json")[1].split("```")[0].strip()
            elif "```" in classification:
                classification = classification.split("```")[1].split("```")[0].strip()

            parsed = json.loads(classification)
            logger.info(f"[ACTION_ORCHESTRATOR] Parsed classification: {parsed}")
            return parsed

        except Exception as e:
            logger.error(f"[ACTION_ORCHESTRATOR] Classification failed: {str(e)}")
            return self._classify_action_fallback(question)

    async def _handle_pending_action_confirmation(
        self,
        pending_action_id: str,
        is_confirmation: bool,
        user_id: str,
        user_role: str,
        session_id: str,
        database_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Handle user confirmation or rejection of a pending action.

        Args:
            pending_action_id: ID of the pending action
            is_confirmation: True if user confirmed, False if rejected
            user_id: User ID
            user_role: User role
            session_id: Session ID
            database_id: User's database_id for correct gateway routing

        Returns:
            Dict with execution result or rejection message
        """
        logger.info(f"[ACTION_ORCHESTRATOR] Handling pending action confirmation: {pending_action_id}")
        logger.info(f"[ACTION_ORCHESTRATOR] User choice: {'CONFIRM' if is_confirmation else 'REJECT'}")

        try:
            # Get the pending action
            pending_action = await pending_actions_store.get_pending_action(pending_action_id)

            if not pending_action:
                logger.warning(f"[ACTION_ORCHESTRATOR] Pending action not found: {pending_action_id}")
                return {
                    "answer": "The action you're trying to confirm has expired or doesn't exist. Please try again.",
                    "success": False,
                    "error": "Pending action not found",
                    "tools_called": [],
                    "awaiting_confirmation": False
                }

            # Check if already resolved
            if pending_action.status != ActionStatus.PENDING:
                logger.warning(f"[ACTION_ORCHESTRATOR] Pending action already resolved: {pending_action.status}")
                return {
                    "answer": f"This action has already been {pending_action.status.value}.",
                    "success": False,
                    "error": f"Action already {pending_action.status.value}",
                    "tools_called": [],
                    "awaiting_confirmation": False
                }

            # Check if expired
            if pending_action.is_expired():
                await pending_actions_store.reject_action(pending_action_id, user_id, "Expired")
                logger.warning(f"[ACTION_ORCHESTRATOR] Pending action expired: {pending_action_id}")
                return {
                    "answer": "This action has expired. Please submit your request again.",
                    "success": False,
                    "error": "Action expired",
                    "tools_called": [],
                    "awaiting_confirmation": False
                }

            if is_confirmation:
                # User confirmed - execute the action
                logger.info(f"[ACTION_ORCHESTRATOR] Executing confirmed action: {pending_action.action_type}")

                # Approve the pending action
                await pending_actions_store.approve_action(pending_action_id, user_id)

                # Execute the action
                result = await self._execute_action_direct(
                    action_type=pending_action.action_type,
                    action_params=pending_action.action_params,
                    user_id=user_id,
                    user_role=user_role,
                    database_id=database_id
                )

                # Mark as executed
                if result.get("success"):
                    await pending_actions_store.mark_executed(pending_action_id, True, "Executed successfully")
                    # Log audit - confirmation and execution
                    audit_logger.log_action_confirmation(
                        user_id=user_id,
                        user_role=user_role,
                        pending_action_id=pending_action_id,
                        approved=True,
                        resolution_note="User confirmed"
                    )
                    audit_logger.log_action_execution(
                        user_id=user_id,
                        user_role=user_role,
                        action_type=pending_action.action_type,
                        tool_name=pending_action.tool_name,
                        success=True,
                        target_user_id=pending_action.action_params.get("target_user_id")
                    )
                else:
                    await pending_actions_store.mark_executed(pending_action_id, False, result.get("error"))
                    audit_logger.log_action_execution(
                        user_id=user_id,
                        user_role=user_role,
                        action_type=pending_action.action_type,
                        tool_name=pending_action.tool_name,
                        success=False,
                        target_user_id=pending_action.action_params.get("target_user_id"),
                        reason=result.get("error", "Unknown error")
                    )

                return {
                    "answer": result.get("answer", "Action completed."),
                    "success": result.get("success", False),
                    "error": result.get("error"),
                    "action_type": pending_action.action_type,
                    "action_params": pending_action.action_params,
                    "tools_called": [pending_action.action_type],
                    "awaiting_confirmation": False
                }

            else:
                # User rejected - cancel the action
                logger.info(f"[ACTION_ORCHESTRATOR] User rejected action: {pending_action.action_type}")
                await pending_actions_store.reject_action(pending_action_id, user_id, "User cancelled")

                # Log audit
                audit_logger.log_action_confirmation(
                    user_id=user_id,
                    user_role=user_role,
                    pending_action_id=pending_action_id,
                    approved=False,
                    resolution_note="User cancelled"
                )

                return {
                    "answer": f"Action cancelled. The {pending_action.action_type.replace('_', ' ')} request has been cancelled.",
                    "success": True,
                    "action_type": pending_action.action_type,
                    "tools_called": [],
                    "awaiting_confirmation": False
                }

        except Exception as e:
            logger.error(f"[ACTION_ORCHESTRATOR] Failed to handle confirmation: {str(e)}", exc_info=True)
            return {
                "answer": f"Error processing confirmation: {str(e)}",
                "success": False,
                "error": str(e),
                "tools_called": [],
                "awaiting_confirmation": False
            }

    async def _execute_action_direct(
        self,
        action_type: str,
        action_params: Dict[str, Any],
        user_id: str,
        user_role: str,
        database_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute an action directly (for non-destructive or confirmed actions)"""
        tool = self.ACTION_TOOLS.get(action_type)
        if not tool:
            return {"success": False, "error": f"Unknown action: {action_type}"}

        try:
            # Build params with user_id and role-specific fields
            params = {
                **action_params,
                "user_id": user_id,  # The invoking user (required by tools)
                "granted_by": user_id,
                "blocked_by": user_id,
                "revoked_by": user_id,
                "database_id": database_id  # Pass database_id for gateway routing
            }
            # Remove user_role from params if it exists (avoid duplicate)
            params.pop("user_role", None)

            logger.info(f"[ACTION_ORCHESTRATOR] Executing {action_type} with database_id={database_id}")
            result = await tool.run(user_role=user_role, **params)

            # Format answer based on result
            answer = self._format_action_result(action_type, result)

            # IMPORTANT: base_tool.run() wraps the result as {"success": True, "result": {...}, "error": None}
            # The actual tool success is in result["result"]["success"], not result["success"]
            # We need to check the inner result for the actual success status
            inner_result = result.get("result", {})
            actual_success = inner_result.get("success", result.get("success", False))
            actual_error = inner_result.get("error") or result.get("error")

            logger.info(f"[ACTION_ORCHESTRATOR] Tool result - wrapper_success={result.get('success')}, actual_success={actual_success}")

            return {
                "success": actual_success,
                "answer": answer,
                "action_result": result,
                "error": actual_error
            }

        except Exception as e:
            logger.error(f"[ACTION_ORCHESTRATOR] Execution failed: {str(e)}")
            return {"success": False, "error": str(e), "answer": f"Action failed: {str(e)}"}

    def _format_action_result(self, action_type: str, result: Dict[str, Any]) -> str:
        """Format action result into human-readable answer"""
        # Note: result is wrapped by base_tool.run() as {"success": True, "result": {...}, "error": None}
        # The actual success/error is in result["result"]
        inner_result = result.get("result", {})
        actual_success = inner_result.get("success", result.get("success", False))
        actual_error = inner_result.get("error") or result.get("error")

        if not actual_success:
            return f"Action failed: {actual_error or 'Unknown error'}"

        result_data = inner_result

        if action_type == "list_access":
            permissions = result_data.get("permissions", [])
            if permissions:
                lines = [f"Access permissions for {result_data.get('user_id', 'user')}:\n"]
                for p in permissions:
                    lines.append(f"- {p.get('target_name', 'Unknown')} ({p.get('access_type', 'N/A')}): {p.get('status', 'N/A')}")
                return "\n".join(lines)
            return f"No active permissions found for user {result_data.get('user_id', 'specified')}."

        elif action_type == "grant_access":
            details = result_data.get("details", {})
            return (f"Access granted successfully.\n\n"
                    f"- User: {details.get('user_id', 'N/A')}\n"
                    f"- Target: {details.get('target_name', 'N/A')}\n"
                    f"- Permission ID: {result_data.get('permission_id', 'N/A')}")

        elif action_type == "block_access":
            details = result_data.get("details", {})
            return (f"Access blocked successfully.\n\n"
                    f"- User: {details.get('user_id', 'N/A')}\n"
                    f"- Target: {details.get('target_name', 'N/A')}")

        elif action_type == "revoke_access":
            return f"Permission revoked successfully.\n\nPermission ID: {result_data.get('permission_id', 'N/A')}"

        # Phase 6 - Extended Access Control Actions
        elif action_type == "register_visitor":
            details = result_data.get("details", {})
            return (f"Visitor registered successfully.\n\n"
                    f"- Visitor ID: {result_data.get('visitor_id', 'N/A')}\n"
                    f"- Visitor ECode: {result_data.get('visitor_ecode', 'N/A')}\n"
                    f"- Name: {details.get('first_name', '')} {details.get('last_name', '')}\n"
                    f"- Card: {details.get('issued_card_number', 'N/A')}")

        elif action_type == "assign_temporary_card":
            details = result_data.get("details", {})
            return (f"Temporary card assigned successfully.\n\n"
                    f"- Card: {result_data.get('card_number', 'N/A')}\n"
                    f"- Assigned to: {result_data.get('assigned_to', 'N/A')}\n"
                    f"- Expiry: {result_data.get('expiry', 'N/A')}")

        elif action_type == "database_backup":
            details = result_data.get("details", {})
            return (f"Database backup completed successfully.\n\n"
                    f"- File: {result_data.get('backup_file_path', 'N/A')}\n"
                    f"- Size: {result_data.get('backup_size_mb', 'N/A')} MB\n"
                    f"- Duration: {result_data.get('backup_duration_seconds', 'N/A')} seconds")

        elif action_type == "enroll_card":
            details = result_data.get("details", {})
            # Check if this was simple enrollment (has old_card/verified) vs full enrollment (has doors_configured)
            if "old_card" in result_data or "verified" in result_data:
                # Simple card enrollment response
                old_card_info = f"- Previous card: {result_data.get('old_card', 'None')}\n" if result_data.get('old_card') else ""
                verified_info = "- Card verified in database" if result_data.get('verified') else ""
                return (f"Card enrolled successfully.\n\n"
                        f"- Card: {result_data.get('card_number', 'N/A')}\n"
                        f"- Employee: {result_data.get('employee_id', 'N/A')}\n"
                        f"{old_card_info}{verified_info}")
            else:
                # Full enrollment with door access response
                return (f"Card enrolled successfully.\n\n"
                        f"- Card: {result_data.get('card_number', 'N/A')}\n"
                        f"- Employee: {result_data.get('employee_id', 'N/A')}\n"
                        f"- Doors configured: {result_data.get('doors_configured', 0)}\n"
                        f"- Failed doors: {result_data.get('failed_doors', [])}")

        elif action_type == "enroll_employee":
            details = result_data.get("details", {})
            return (f"Employee enrolled successfully.\n\n"
                    f"- ECode: {result_data.get('ecode', 'N/A')}\n"
                    f"- Corp Employee Code: {result_data.get('corp_emp_code', 'N/A')}\n"
                    f"- Card enrolled: {result_data.get('card_enrolled', False)}")

        elif action_type == "manage_door_access":
            details = result_data.get("details", {})
            action = result_data.get("action", "N/A")
            return (f"Door access {action} successfully.\n\n"
                    f"- Employee: {result_data.get('employee_id', 'N/A')}\n"
                    f"- Doors affected: {result_data.get('doors_affected', 0)}\n"
                    f"- Failed doors: {result_data.get('failed_doors', [])}")

        elif action_type == "manage_authentication":
            action = result_data.get("action", "N/A")
            auth_name = result_data.get("authentication_name", "N/A")
            return (f"Authentication {action} completed successfully.\n\n"
                    f"- Employee: {result_data.get('employee_id', 'N/A')}\n"
                    f"- Authentication Type: {auth_name}\n"
                    f"- Terminals affected: {result_data.get('terminals_affected', 0)}\n"
                    f"- Failed terminals: {result_data.get('failed_terminals', [])}")

        elif action_type == "trigger_biometric_enrollment":
            biometric_type = result_data.get("biometric_type", "N/A")
            terminal_name = result_data.get("terminal_name", "N/A")
            timeout = result_data.get("timeout_seconds", 60)
            instructions = result_data.get("instructions", "")

            # Check if enrollment actually succeeded or failed
            if result_data.get("success"):
                return (f"**Biometric enrollment completed successfully!**\n\n"
                        f"- Employee: {result_data.get('employee_id', 'N/A')} ({result_data.get('employee_name', '')})\n"
                        f"- Biometric Type: {biometric_type}\n"
                        f"- Terminal: {terminal_name}\n"
                        f"- Status: {result_data.get('message', 'Enrolled successfully')}\n\n"
                        f"{instructions}")
            else:
                # Enrollment failed (timeout, device issue, etc.)
                error_msg = result_data.get("error") or result_data.get("message") or "Unknown error"
                return (f"**Biometric enrollment FAILED**\n\n"
                        f"- Employee: {result_data.get('employee_id', 'N/A')}\n"
                        f"- Biometric Type: {biometric_type}\n"
                        f"- Terminal: {terminal_name}\n"
                        f"- Error: {error_msg}\n\n"
                        f"**Please try again.** Make sure the employee places their palm/finger on the device within the {timeout}-second timeout period.")

        elif action_type == "employee_action":
            # employee_action tool returns data at top level, not nested in "result"
            action = result.get("action") or result_data.get("action", "unknown")
            ecode = result.get("ecode") or result_data.get("ecode", "N/A")
            employee_name = result.get("employee_name") or result_data.get("employee_name", "")
            message = result.get("message") or result_data.get("message", "")

            if result.get("success"):
                # Fix grammar: "activated" not "activateed"
                action_past = "activated" if action == "activate" else "deactivated"
                action_result_text = "can now clock in/out at biometric devices" if action == "activate" else "can no longer clock in/out at biometric devices"

                return (f"**Employee {action_past.capitalize()} Successfully!**\n\n"
                        f"- Employee: {employee_name or ecode}\n"
                        f"- ECode: {ecode}\n"
                        f"- Action: {action.upper()}\n"
                        f"- Status: Completed\n\n"
                        f"The employee {action_result_text}.")
            else:
                error_msg = result.get("error", "Unknown error")
                return (f"**Employee Action FAILED**\n\n"
                        f"- Action: {action}\n"
                        f"- ECode: {ecode}\n"
                        f"- Error: {error_msg}")

        elif action_type == "employee_blacklist":
            # employee_blacklist tool returns data at top level
            action = result.get("action") or result_data.get("action", "unknown")
            ecode = result.get("ecode") or result_data.get("ecode", "N/A")
            employee_name = result.get("employee_name") or result_data.get("employee_name", "")
            message = result.get("message") or result_data.get("message", "")
            reason = result.get("reason") or result_data.get("reason", "")

            if result.get("success"):
                if action in ["remove_blacklist", "unblacklist"]:
                    action_past = "Removed from Blacklist"
                    action_result_text = "has been removed from the blacklist and can now access Oryggi systems"
                else:
                    action_past = "Blacklisted"
                    action_result_text = "has been blacklisted and can no longer access any Oryggi systems"

                result_text = (f"**Employee {action_past} Successfully!**\n\n"
                        f"- Employee: {employee_name or ecode}\n"
                        f"- ECode: {ecode}\n"
                        f"- Action: {action.upper().replace('_', ' ')}\n"
                        f"- Status: Completed\n")
                if reason:
                    result_text += f"- Reason: {reason}\n"
                result_text += f"\nThe employee {action_result_text}."
                return result_text
            else:
                error_msg = result.get("error", "Unknown error")
                return (f"**Employee Blacklist Action FAILED**\n\n"
                        f"- Action: {action}\n"
                        f"- ECode: {ecode}\n"
                        f"- Error: {error_msg}")

        elif action_type == "employee_terminate":
            # employee_terminate tool returns data at top level
            action = result.get("action") or result_data.get("action", "unknown")
            ecode = result.get("ecode") or result_data.get("ecode", "N/A")
            employee_name = result.get("employee_name") or result_data.get("employee_name", "")
            message = result.get("message") or result_data.get("message", "")
            reason = result.get("reason") or result_data.get("reason", "")
            leaving_date = result.get("leaving_date") or result_data.get("leaving_date", "")

            if result.get("success"):
                if action in ["un_terminate", "unterminate", "reinstate"]:
                    action_past = "Un-terminated (Reinstated)"
                    action_result_text = "has been reinstated and can now access Oryggi systems again"
                else:
                    action_past = "Terminated"
                    action_result_text = "has been terminated and can no longer access any Oryggi systems"

                result_text = (f"**Employee {action_past} Successfully!**\n\n"
                        f"- Employee: {employee_name or ecode}\n"
                        f"- ECode: {ecode}\n"
                        f"- Action: {action.upper().replace('_', ' ')}\n"
                        f"- Status: Completed\n")
                if reason:
                    result_text += f"- Reason: {reason}\n"
                if leaving_date and action == "terminate":
                    result_text += f"- Leaving Date: {leaving_date}\n"
                result_text += f"\nThe employee {action_result_text}."
                return result_text
            else:
                error_msg = result.get("error", "Unknown error")
                return (f"**Employee Terminate Action FAILED**\n\n"
                        f"- Action: {action}\n"
                        f"- ECode: {ecode}\n"
                        f"- Error: {error_msg}")

        return "Action completed successfully."

    async def resume_with_confirmation(
        self,
        thread_id: str,
        confirmed: bool,
        reason: Optional[str] = None,
        action_type: Optional[str] = None,
        action_params: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        user_role: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Resume and execute action after user confirmation (simplified approach)

        Args:
            thread_id: Thread ID from original request
            confirmed: Whether user confirmed the action
            reason: Reason for rejection (if confirmed=False)
            action_type: Type of action to execute
            action_params: Parameters for the action
            user_id: User ID
            user_role: User's role

        Returns:
            Final result after execution
        """
        logger.info(f"[ACTION_ORCHESTRATOR] Resume: thread={thread_id}, confirmed={confirmed}")

        # If rejected, just return cancellation message
        if not confirmed:
            audit_logger.log_action_confirmation(
                user_id=user_id or "unknown",
                user_role=user_role or "ADMIN",
                pending_action_id=thread_id,
                approved=False,
                resolution_note=reason
            )
            return {
                "answer": f"Action cancelled. {reason or ''}".strip(),
                "success": True,  # Cancellation is successful
                "error": None,
                "tools_called": [],
                "action_type": action_type,
                "action_result": None,
                "awaiting_confirmation": False
            }

        # If confirmed, execute the action
        if not action_type or not action_params:
            # Try to get from pending actions store
            actions = await pending_actions_store.get_pending_actions()
            for action in actions:
                if action.langgraph_thread_id == thread_id:
                    action_type = action.action_type
                    action_params = action.action_params
                    user_id = user_id or action.user_id
                    user_role = user_role or action.user_role
                    break

        if not action_type:
            return {
                "answer": "Could not find the action to execute.",
                "success": False,
                "error": "Action not found",
                "awaiting_confirmation": False
            }

        logger.info(f"[ACTION_ORCHESTRATOR] Executing confirmed action: {action_type}")

        # Log approval
        audit_logger.log_action_confirmation(
            user_id=user_id or "unknown",
            user_role=user_role or "ADMIN",
            pending_action_id=thread_id,
            approved=True
        )

        # Execute the action
        result = await self._execute_action_direct(
            action_type=action_type,
            action_params=action_params or {},
            user_id=user_id or "unknown",
            user_role=user_role or "ADMIN"
        )

        return {
            "answer": result.get("answer", ""),
            "success": result.get("success", True),
            "error": result.get("error"),
            "tools_called": [action_type] if result.get("success") else [],
            "action_type": action_type,
            "action_result": result.get("action_result"),
            "awaiting_confirmation": False
        }

    def is_action_request(self, question: str) -> bool:
        """
        Quick check if a question is likely an action request

        Used by main orchestrator to route to action workflow
        """
        action_keywords = [
            # Phase 5 - Original access control keywords
            'grant', 'give access', 'allow', 'provide access',
            'block', 'deny', 'stop access', 'prevent',
            'revoke', 'remove access', 'delete permission',
            'list access', 'show permissions', 'what access',
            # Phase 6 - Extended access control keywords
            'register visitor', 'register a visitor', 'add visitor', 'add a visitor',
            'new visitor', 'visitor registration', 'create visitor',
            'temporary card', 'temp card', 'assign card', 'visitor card',
            'database backup', 'backup database', 'backup oryggi', 'db backup', 'backup the database',
            'enroll card', 'card enrollment', 'assign access card', 'issue card',
            'enroll employee', 'add employee', 'new employee', 'employee enrollment',
            'create employee', 'register employee',
            'door access', 'specific door', 'grant door', 'block door', 'manage door',
            # Authentication management keywords
            'add authentication', 'remove authentication', 'set authentication',
            'manage authentication', 'authentication type',
            'fusion', 'palm', 'fingerprint', 'face only', 'finger only',
            'card only', 'card + face', 'card + finger', 'card + palm',
            'enable fingerprint', 'enable face', 'enable palm',
            'disable fingerprint', 'disable face', 'disable palm',
            # Biometric enrollment keywords
            'enroll biometric', 'biometric enrollment', 'trigger enrollment',
            'enroll face', 'enroll palm', 'enroll finger', 'enroll fingerprint',
            'start enrollment', 'begin enrollment', 'capture biometric',
            'face enrollment', 'palm enrollment', 'finger enrollment',
            'fingerprint enrollment', 'biometric capture',
            # Phase 7 - Employee action keywords (Activate/Deactivate)
            'activate employee', 'deactivate employee', 'activate user',
            'deactivate user', 'enable employee', 'disable employee',
            'activate ecode', 'deactivate ecode',
            # Phase 8 - Employee blacklist keywords
            'blacklist employee', 'blacklist user', 'blacklist ecode',
            'add to blacklist', 'remove from blacklist', 'unblacklist',
            'remove blacklist', 'blacklist',
            # Phase 9 - Employee terminate keywords
            'terminate employee', 'terminate user', 'terminate ecode',
            'un-terminate', 'unterminate', 'reinstate employee'
        ]
        question_lower = question.lower()
        return any(kw in question_lower for kw in action_keywords)


# Global orchestrator instance
action_orchestrator = ActionOrchestrator()
