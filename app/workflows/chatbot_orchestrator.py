"""
LangGraph Multi-Tool Orchestrator
Routes user requests to appropriate tools (query, report, email)

Includes Clarity Assessment for handling unclear/ambiguous prompts.
"""

from typing import Any, Dict, List, Optional, TypedDict, Annotated
from langgraph.graph import StateGraph, END
import operator
import asyncio
from loguru import logger
import google.generativeai as genai

from app.config import settings
from app.tools.query_database_tool import query_database_tool
from app.tools.generate_report_tool import generate_report_tool
from app.tools.email_tools import send_email_tool

# Phase 5/6: Access Control Action Orchestrator
from app.workflows.action_orchestrator import action_orchestrator
from app.services.pending_actions_store import pending_actions_store, ActionStatus

# Clarity Assessment for unclear prompts
from app.services.clarity_assessor import clarity_assessor, ClarityAssessment, ClarificationQuestion

# PERFORMANCE: Import at module level instead of inside methods
from app.memory.conversation_store import ConversationStore

# PERFORMANCE: Singleton instance to avoid repeated instantiation
_conversation_store = None

def get_conversation_store() -> ConversationStore:
    """Get singleton ConversationStore instance for performance."""
    global _conversation_store
    if _conversation_store is None:
        _conversation_store = ConversationStore()
    return _conversation_store


class ChatbotState(TypedDict):
    """
    State for LangGraph chatbot workflow

    Tracks user request, intent classification, tool executions, and results
    """
    # Input
    question: str
    user_id: str
    user_role: str
    session_id: str

    # Clarity Assessment (Phase: Clarification)
    is_clear: bool  # Whether the question is clear enough to process
    clarity_confidence: float  # Confidence score 0-1
    needs_clarification: bool  # Whether to ask for clarification
    clarification_question: Optional[str]  # Question to ask user
    clarification_options: Optional[List[str]]  # Options for user to choose
    clarification_attempt: int  # Current attempt number (1-3)
    max_clarification_attempts: int  # Maximum attempts (default 3)
    original_question: Optional[str]  # Original question before clarification

    # Intent classification
    intent: str  # "query", "report", "email", or "combined"
    report_format: Optional[str]  # "pdf" or "excel"
    email_recipient: Optional[str]

    # Tool execution tracking
    tools_called: Annotated[List[str], operator.add]
    query_result: Optional[Dict[str, Any]]
    report_result: Optional[Dict[str, Any]]
    email_result: Optional[Dict[str, Any]]

    # Output
    answer: str
    success: bool
    error: Optional[str]

    # PERFORMANCE: Cached conversation history to avoid duplicate DB queries
    conversation_history: Optional[List[Dict[str, Any]]]

    # PERFORMANCE: Pre-computed intent from parallel execution
    precomputed_intent: Optional[Dict[str, Any]]


class ChatbotOrchestrator:
    """
    LangGraph-based multi-tool orchestrator

    Workflow:
    1. Classify Intent -> Determine what user wants (query/report/email/combined)
    2. Route to Tools -> Execute appropriate tools based on intent
    3. Format Response -> Return structured answer to user

    Examples:
        - "Show me top 10 employees" -> Query tool
        - "Generate a PDF report of recent hires" -> Query + Report tools
        - "Email me an Excel report of active employees" -> Query + Report + Email tools
    """

    def __init__(self):
        """Initialize orchestrator with Gemini for intent classification"""
        genai.configure(api_key=settings.gemini_api_key)
        self.model = genai.GenerativeModel(settings.gemini_model)

        # Build LangGraph state machine
        self.workflow = self._build_workflow()

    def _build_workflow(self) -> StateGraph:
        """
        Build LangGraph state machine for multi-tool orchestration

        Workflow Graph (Updated with Clarity Assessment):
            START
              ↓
        assess_clarity ──────────┐
              ↓                  │
        [IS CLEAR?]              │
              ↓ YES              ↓ NO
        classify_intent    return_clarification
              ↓                  ↓
        ┌─────┴─────┐          END
        │           │
   execute_query    END (if just email with no data needed)
        │
        ├──-> execute_report (if "report" or "combined")
        │
        └──-> execute_email (if email_recipient provided)
              ↓
        format_response
              ↓
            END
        """
        workflow = StateGraph(ChatbotState)

        # Add nodes (including clarity assessment)
        workflow.add_node("assess_clarity", self._assess_clarity)
        workflow.add_node("return_clarification", self._return_clarification)
        workflow.add_node("classify_intent", self._classify_intent)
        workflow.add_node("execute_query", self._execute_query)
        workflow.add_node("execute_report", self._execute_report)
        workflow.add_node("execute_email", self._execute_email)
        workflow.add_node("format_response", self._format_response)

        # Define edges - START with clarity assessment
        workflow.set_entry_point("assess_clarity")

        # After clarity assessment, route based on clarity
        workflow.add_conditional_edges(
            "assess_clarity",
            self._route_after_clarity,
            {
                "clear": "classify_intent",
                "unclear": "return_clarification"
            }
        )

        # Return clarification goes to END
        workflow.add_edge("return_clarification", END)

        # After intent classification, route to appropriate tool
        workflow.add_conditional_edges(
            "classify_intent",
            self._route_after_intent,
            {
                "query_only": "execute_query",
                "report": "execute_query",  # Report needs query results first
                "combined": "execute_query",  # Combined needs query + report + email
                "end": END  # No tools needed (rare edge case)
            }
        )

        # After query execution, check if report is needed
        workflow.add_conditional_edges(
            "execute_query",
            self._route_after_query,
            {
                "report": "execute_report",
                "no_report": "format_response"
            }
        )

        # After report generation, check if email is needed
        workflow.add_conditional_edges(
            "execute_report",
            self._route_after_report,
            {
                "email": "execute_email",
                "no_email": "format_response"
            }
        )

        # After email, format final response
        workflow.add_edge("execute_email", "format_response")
        workflow.add_edge("format_response", END)

        return workflow.compile()

    async def _assess_clarity(self, state: ChatbotState) -> ChatbotState:
        """
        Step 0: Assess if the user's prompt is clear enough to process.

        Uses hybrid approach:
        1. Fast heuristics for obvious unclear cases
        2. LLM-based assessment for nuanced cases

        PERFORMANCE OPTIMIZED:
        - Uses singleton ConversationStore and caches history in state
        - Runs clarity assessment AND intent classification in PARALLEL
          This saves 2-5 seconds by overlapping two LLM calls
        """
        logger.info(f"[ORCHESTRATOR:CLARITY] Assessing clarity for: {state['question']}")

        try:
            # PERFORMANCE: Get conversation history once and cache in state
            # This avoids duplicate DB queries in _execute_query
            conversation_history = state.get("conversation_history") or []
            if not conversation_history:
                try:
                    conversation_store = get_conversation_store()  # Use singleton
                    history = conversation_store.get_session_history(
                        session_id=state["session_id"],
                        user_id=state["user_id"],
                        limit=10  # Get 10 to cover both clarity (5) and query (10) needs
                    )
                    conversation_history = history
                    state["conversation_history"] = history  # Cache in state
                    logger.debug(f"[ORCHESTRATOR:CLARITY] Cached {len(history)} messages in state")
                except Exception as e:
                    logger.warning(f"[ORCHESTRATOR:CLARITY] Failed to get history: {e}")

            # PERFORMANCE OPTIMIZATION: Run clarity and intent classification in PARALLEL
            # This saves 2-5 seconds by overlapping two LLM calls
            # Intent result will be used later if clarity passes
            logger.info("[ORCHESTRATOR:PARALLEL] Running clarity + intent in parallel")

            # Create parallel tasks
            clarity_task = clarity_assessor.assess_clarity(
                question=state["question"],
                conversation_history=conversation_history
            )
            intent_task = self._classify_intent_async(state["question"])

            # Run both tasks concurrently
            assessment, intent_result = await asyncio.gather(
                clarity_task,
                intent_task,
                return_exceptions=True  # Don't fail if one fails
            )

            # Handle potential exceptions from gather
            if isinstance(assessment, Exception):
                logger.error(f"[ORCHESTRATOR:PARALLEL] Clarity assessment failed: {assessment}")
                # Default to clear on error
                state["is_clear"] = True
                state["clarity_confidence"] = 0.5
                state["needs_clarification"] = False
                assessment = None
            else:
                state["is_clear"] = assessment.is_clear
                state["clarity_confidence"] = assessment.confidence

            if isinstance(intent_result, Exception):
                logger.error(f"[ORCHESTRATOR:PARALLEL] Intent classification failed: {intent_result}")
                intent_result = None
            else:
                # Store pre-computed intent for later use
                state["precomputed_intent"] = intent_result
                logger.info(f"[ORCHESTRATOR:PARALLEL] Pre-computed intent: {intent_result.get('intent', 'unknown')}")

            # Process clarity result if we have it
            if assessment and not assessment.is_clear:
                logger.info(f"[ORCHESTRATOR:CLARITY] Question is UNCLEAR (confidence={assessment.confidence})")
                logger.info(f"[ORCHESTRATOR:CLARITY] Reason: {assessment.reason}")
                logger.info(f"[ORCHESTRATOR:CLARITY] Missing: {assessment.missing_info}")

                # Generate clarifying question with options
                clarification = await clarity_assessor.generate_clarifying_question(
                    question=state["question"],
                    assessment=assessment,
                    previous_clarifications=None  # TODO: Get from session state
                )

                state["needs_clarification"] = True
                state["clarification_question"] = clarification.question
                state["clarification_options"] = clarification.options
                state["original_question"] = state["question"]

                logger.info(f"[ORCHESTRATOR:CLARITY] Clarification question: {clarification.question}")
                logger.info(f"[ORCHESTRATOR:CLARITY] Options: {clarification.options}")
            elif assessment:
                logger.info(f"[ORCHESTRATOR:CLARITY] Question is CLEAR (confidence={assessment.confidence})")
                state["needs_clarification"] = False

            return state

        except Exception as e:
            logger.error(f"[ORCHESTRATOR:CLARITY] Assessment failed: {e}")
            # On error, assume clear and proceed (don't block user)
            state["is_clear"] = True
            state["clarity_confidence"] = 0.5
            state["needs_clarification"] = False
            return state

    def _route_after_clarity(self, state: ChatbotState) -> str:
        """Routing logic after clarity assessment"""
        needs_clarification = state.get("needs_clarification", False)
        clarification_attempt = state.get("clarification_attempt", 1)
        max_attempts = state.get("max_clarification_attempts", 3)

        logger.info(f"[ORCHESTRATOR:ROUTE] After clarity: needs_clarification={needs_clarification}, attempt={clarification_attempt}")

        if needs_clarification and clarification_attempt <= max_attempts:
            logger.info("[ORCHESTRATOR:ROUTE] Routing to 'unclear' (will ask clarification)")
            return "unclear"
        else:
            logger.info("[ORCHESTRATOR:ROUTE] Routing to 'clear' (proceed with intent classification)")
            return "clear"

    def _return_clarification(self, state: ChatbotState) -> ChatbotState:
        """
        Return clarification request to user.
        This node formats the response asking for clarification.
        """
        logger.info("[ORCHESTRATOR:CLARIFICATION] Preparing clarification response")

        question = state.get("clarification_question", "Could you please provide more details?")
        options = state.get("clarification_options", [])
        attempt = state.get("clarification_attempt", 1)
        max_attempts = state.get("max_clarification_attempts", 3)

        # Format the answer as a clarification request
        answer_parts = [question]

        if options:
            answer_parts.append("\n\nHere are some options you can choose from:")
            for i, option in enumerate(options, 1):
                answer_parts.append(f"\n  {i}. {option}")

        if attempt > 1:
            answer_parts.append(f"\n\n(Clarification attempt {attempt} of {max_attempts})")

        state["answer"] = "".join(answer_parts)
        state["success"] = True  # Clarification request is a successful response
        state["tools_called"] = ["clarity_assessment"]

        logger.info(f"[ORCHESTRATOR:CLARIFICATION] Response prepared with {len(options)} options")

        return state

    def _classify_intent_fallback(self, question: str) -> Dict[str, Any]:
        """
        Fallback intent classifier using keyword matching
        Used when Gemini API is unavailable
        """
        import re
        question_lower = question.lower()

        # Extract email if present
        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', question_lower)
        email_recipient = email_match.group(0) if email_match else None

        # Detect report intent
        report_keywords = ['report', 'generate', 'create', 'pdf', 'excel', 'spreadsheet']
        has_report = any(kw in question_lower for kw in report_keywords)

        # Detect email intent
        email_keywords = ['email', 'send', 'share']
        has_email = any(kw in question_lower for kw in email_keywords) or email_recipient

        # Detect report format (Excel only)
        report_format = None
        if has_report:
            # Always use Excel format (PDF support removed)
            report_format = 'excel'

        # Determine combined intent
        if has_report and (has_email or email_recipient):
            intent = "combined"
        elif has_report:
            intent = "report"
        elif has_email or email_recipient:
            intent = "email"
        else:
            intent = "query"

        # Handle "email me" case
        if not email_recipient and has_email:
            email_recipient = "user_email"

        return {
            "intent": intent,
            "report_format": report_format,
            "email_recipient": email_recipient
        }

    def _classify_intent(self, state: ChatbotState) -> ChatbotState:
        """
        Step 1: Classify user intent using Gemini

        Determines:
        - Intent type: query, report, email, or combined
        - Report format: pdf or excel (if report requested)
        - Email recipient (if email requested)

        PERFORMANCE OPTIMIZED: Uses pre-computed intent from parallel execution
        if available, skipping redundant LLM call.
        """
        logger.info(f"[ORCHESTRATOR] Classifying intent for: {state['question']}")

        # PERFORMANCE: Check for pre-computed intent from parallel execution
        precomputed = state.get("precomputed_intent")
        if precomputed:
            logger.info("[ORCHESTRATOR:PARALLEL] Using pre-computed intent (saved LLM call)")
            state["intent"] = precomputed.get("intent", "query")
            state["report_format"] = precomputed.get("report_format")
            state["email_recipient"] = precomputed.get("email_recipient")
            logger.info(
                f"[ORCHESTRATOR] Intent from cache: {state['intent']}, "
                f"format={state['report_format']}, email={state['email_recipient']}"
            )
            return state

        # Fallback: Run classification if not pre-computed
        logger.info("[ORCHESTRATOR] No pre-computed intent, running LLM classification")
        try:
            prompt = f"""Analyze this user request and classify the intent.

USER REQUEST:
{state['question']}

CLASSIFICATION TASK:
Determine the user's intent and extract key parameters.

INTENT TYPES:
1. "query" - User wants data/answer (e.g., "How many employees?", "Show me top 10 sales")
2. "report" - User wants a generated report (e.g., "Generate a PDF report of...", "Create Excel spreadsheet of...")
3. "email" - User wants to send data via email (e.g., "Email me...", "Send report to...")
4. "combined" - Multiple intents (e.g., "Generate PDF report and email it to manager@company.com")

REPORT FORMAT (if report intent):
- "pdf" or "excel"

EMAIL RECIPIENT (if email intent):
- Extract email address from request (e.g., "manager@company.com")
- If user says "email me" or "send to me", return "user_email" as placeholder

Return ONLY a JSON object with this exact structure:
{{
  "intent": "query|report|email|combined",
  "report_format": "pdf|excel|null",
  "email_recipient": "email@example.com|user_email|null"
}}

EXAMPLES:
Request: "How many employees joined last month?"
Response: {{"intent": "query", "report_format": null, "email_recipient": null}}

Request: "Generate a PDF report of top 10 sales by region"
Response: {{"intent": "report", "report_format": "pdf", "email_recipient": null}}

Request: "Email me an Excel report of active employees"
Response: {{"intent": "combined", "report_format": "excel", "email_recipient": "user_email"}}

Request: "Create a PDF report of Q4 revenue and send it to manager@company.com"
Response: {{"intent": "combined", "report_format": "pdf", "email_recipient": "manager@company.com"}}

Now classify this request:
{state['question']}

JSON Response:"""

            response = self.model.generate_content(prompt)
            classification = response.text.strip()

            # Parse JSON response
            import json
            # Remove markdown code blocks if present
            if "```json" in classification:
                classification = classification.split("```json")[1].split("```")[0].strip()
            elif "```" in classification:
                classification = classification.split("```")[1].split("```")[0].strip()

            result = json.loads(classification)

            # Update state
            state["intent"] = result.get("intent", "query")
            state["report_format"] = result.get("report_format")
            state["email_recipient"] = result.get("email_recipient")

            logger.info(
                f"[ORCHESTRATOR] Intent classified: {state['intent']}, "
                f"format={state['report_format']}, email={state['email_recipient']}"
            )

            return state

        except Exception as e:
            logger.error(f"[ORCHESTRATOR] Intent classification failed: {str(e)}")
            logger.info("[ORCHESTRATOR] Using fallback keyword-based intent classifier")
            # Use fallback classifier
            result = self._classify_intent_fallback(state['question'])
            state["intent"] = result.get("intent", "query")
            state["report_format"] = result.get("report_format")
            state["email_recipient"] = result.get("email_recipient")
            logger.info(
                f"[ORCHESTRATOR] Fallback intent classified: {state['intent']}, "
                f"format={state['report_format']}, email={state['email_recipient']}"
            )
            return state

    async def _classify_intent_async(self, question: str) -> Dict[str, Any]:
        """
        PERFORMANCE OPTIMIZED: Async intent classification for parallel execution.

        Runs the LLM call in a thread pool to enable parallel execution with
        clarity assessment. Returns raw classification result.
        """
        try:
            prompt = f"""Analyze this user request and classify the intent.

USER REQUEST:
{question}

CLASSIFICATION TASK:
Determine the user's intent and extract key parameters.

INTENT TYPES:
1. "query" - User wants data/answer (e.g., "How many employees?", "Show me top 10 sales")
2. "report" - User wants a generated report (e.g., "Generate a PDF report of...", "Create Excel spreadsheet of...")
3. "email" - User wants to send data via email (e.g., "Email me...", "Send report to...")
4. "combined" - Multiple intents (e.g., "Generate PDF report and email it to manager@company.com")

REPORT FORMAT (if report intent):
- "pdf" or "excel"

EMAIL RECIPIENT (if email intent):
- Extract email address from request (e.g., "manager@company.com")
- If user says "email me" or "send to me", return "user_email" as placeholder

Return ONLY a JSON object with this exact structure:
{{
  "intent": "query|report|email|combined",
  "report_format": "pdf|excel|null",
  "email_recipient": "email@example.com|user_email|null"
}}

JSON Response:"""

            # Run blocking LLM call in thread pool
            response = await asyncio.to_thread(self.model.generate_content, prompt)
            classification = response.text.strip()

            # Parse JSON response
            import json
            if "```json" in classification:
                classification = classification.split("```json")[1].split("```")[0].strip()
            elif "```" in classification:
                classification = classification.split("```")[1].split("```")[0].strip()

            result = json.loads(classification)
            logger.debug(f"[ORCHESTRATOR:PARALLEL] Intent classification completed: {result.get('intent')}")
            return result

        except Exception as e:
            logger.error(f"[ORCHESTRATOR:PARALLEL] Async intent classification failed: {e}")
            # Return fallback result
            return self._classify_intent_fallback(question)

    def _route_after_intent(self, state: ChatbotState) -> str:
        """Routing logic after intent classification"""
        intent = state.get("intent", "query")
        logger.info(f"[ORCHESTRATOR:ROUTE] After intent classification: intent={intent}")

        if intent in ["report", "combined", "email"]:
            logger.info(f"[ORCHESTRATOR:ROUTE] Routing to 'report' (will execute query first for {intent})")
            return "report"  # Will execute query first, then report (and email if needed)
        elif intent == "query":
            logger.info("[ORCHESTRATOR:ROUTE] Routing to 'query_only'")
            return "query_only"
        else:
            logger.info("[ORCHESTRATOR:ROUTE] Routing to 'end' (no tools needed)")
            return "end"

    async def _execute_query(self, state: ChatbotState) -> ChatbotState:
        """
        Step 2: Execute database query using query_database_tool

        PERFORMANCE OPTIMIZED: Uses cached conversation history from state
        instead of making duplicate DB query
        """
        logger.info(f"[ORCHESTRATOR] Executing query for: {state['question']}")

        try:
            # PERFORMANCE: Use cached conversation history from state (set in _assess_clarity)
            # This eliminates duplicate DB query
            conversation_history = state.get("conversation_history") or []
            if conversation_history:
                logger.debug(f"[ORCHESTRATOR] Using cached conversation history: {len(conversation_history)} messages")
            else:
                # Fallback: fetch if not cached (shouldn't happen in normal flow)
                try:
                    conversation_store = get_conversation_store()  # Use singleton
                    history = conversation_store.get_session_history(
                        session_id=state["session_id"],
                        user_id=state["user_id"],
                        limit=10
                    )
                    conversation_history = history
                    state["conversation_history"] = history  # Cache for future use
                    logger.debug(f"[ORCHESTRATOR] Fetched and cached {len(history)} messages")
                except Exception as e:
                    logger.warning(f"[ORCHESTRATOR] Failed to retrieve conversation history: {e}")

            result = await query_database_tool.run(
                user_role=state["user_role"],
                question=state["question"],
                user_id=state["user_id"],
                conversation_history=conversation_history
            )

            state["query_result"] = result
            state["tools_called"] = ["query_database"]

            if result.get("success"):
                logger.info(f"[ORCHESTRATOR] Query successful: {result.get('result', {}).get('result_count', 0)} rows")
            else:
                logger.warning(f"[ORCHESTRATOR] Query failed: {result.get('error')}")
                state["success"] = False
                state["error"] = result.get("error")

            return state

        except Exception as e:
            logger.error(f"[ORCHESTRATOR] Query execution failed: {str(e)}")
            state["success"] = False
            state["error"] = str(e)
            state["query_result"] = {"success": False, "error": str(e)}
            return state

    def _route_after_query(self, state: ChatbotState) -> str:
        """Routing logic after query execution"""
        intent = state.get("intent", "query")
        logger.info(f"[ORCHESTRATOR:ROUTE] After query execution: intent={intent}")

        # FIXED BUG #2: Added "email" to routing logic
        if intent in ["report", "combined", "email"]:
            logger.info("[ORCHESTRATOR:ROUTE] Routing to 'report' node (will execute report/email)")
            return "report"
        else:
            logger.info("[ORCHESTRATOR:ROUTE] Routing to 'no_report' (skip to format_response)")
            return "no_report"

    async def _execute_report(self, state: ChatbotState) -> ChatbotState:
        """
        Step 3: Generate report using generate_report_tool
        """
        logger.info(f"[ORCHESTRATOR] Generating {state['report_format']} report")

        try:
            result = await generate_report_tool.run(
                user_role=state["user_role"],
                question=state["question"],
                user_id=state["user_id"],
                format=state["report_format"] or "excel",
                email_to=None,  # Will handle email separately
                query_result=state["query_result"]  # Pass pre-computed query results
            )

            state["report_result"] = result
            state["tools_called"].append("generate_report")

            # Check BOTH outer and inner success status (tools return double-wrapped results)
            inner_result = result.get("result", {})
            if result.get("success") and inner_result.get("success"):
                logger.info(f"[ORCHESTRATOR] Report generated: {inner_result.get('report_path')}")
            else:
                # Extract error from inner or outer result
                error_msg = inner_result.get("error") or result.get("error", "Unknown error")
                logger.warning(f"[ORCHESTRATOR] Report generation failed: {error_msg}")
                state["success"] = False
                state["error"] = error_msg

            return state

        except Exception as e:
            logger.error(f"[ORCHESTRATOR] Report generation failed: {str(e)}")
            state["report_result"] = {"success": False, "error": str(e)}
            return state

    def _route_after_report(self, state: ChatbotState) -> str:
        """Routing logic after report generation"""
        email_recipient = state.get("email_recipient")
        logger.info(f"[ORCHESTRATOR:ROUTE] After report generation: email_recipient={email_recipient}")

        if email_recipient:
            logger.info("[ORCHESTRATOR:ROUTE] Routing to 'email' node")
            return "email"
        else:
            logger.info("[ORCHESTRATOR:ROUTE] Routing to 'no_email' (skip to format_response)")
            return "no_email"

    async def _execute_email(self, state: ChatbotState) -> ChatbotState:
        """
        Step 4: Send email using send_email_tool
        """
        logger.info("=" * 80)
        logger.info("[ORCHESTRATOR:EMAIL] ENTERING EMAIL EXECUTION NODE")
        logger.info("=" * 80)

        email_recipient = state["email_recipient"]
        logger.info(f"[ORCHESTRATOR:EMAIL] Email recipient from state: {email_recipient}")
        logger.info(f"[ORCHESTRATOR:EMAIL] User ID: {state['user_id']}")
        logger.info(f"[ORCHESTRATOR:EMAIL] User role: {state['user_role']}")
        logger.info(f"[ORCHESTRATOR:EMAIL] Question: {state['question']}")

        # Handle "user_email" placeholder
        if email_recipient == "user_email":
            # In production, you'd get this from user profile
            # For now, we'll skip email or use a configured default
            logger.warning("[ORCHESTRATOR:EMAIL] User email not configured, skipping email")
            state["email_result"] = {
                "success": False,
                "error": "User email address not configured. Please provide a specific email address."
            }
            logger.info("[ORCHESTRATOR:EMAIL] Returning state with email error")
            return state

        logger.info(f"[ORCHESTRATOR:EMAIL] Preparing to send email to: {email_recipient}")

        try:
            # Get report path from previous step
            logger.debug("[ORCHESTRATOR:EMAIL] Checking for report from previous step...")
            report_result = state.get("report_result", {})
            logger.debug(f"[ORCHESTRATOR:EMAIL] report_result: {report_result}")

            result_data = report_result.get("result", {})
            logger.debug(f"[ORCHESTRATOR:EMAIL] result_data: {result_data}")

            report_path = result_data.get("report_path")
            logger.info(f"[ORCHESTRATOR:EMAIL] Report path from previous step: {report_path}")

            # Prepare email parameters
            subject = f"Report: {state['question'][:50]}"

            # BUG #4 FIX: Handle both scenarios - with and without report attachment
            if report_path:
                # Scenario 1: Report exists - send email with attachment
                logger.info("[ORCHESTRATOR:EMAIL] Report path found - email will include attachment")
                body_html = f"<p>Please find the requested report attached.</p><p><strong>Question:</strong> {state['question']}</p>"
                attachment_path = report_path
            else:
                # Scenario 2: No report - send email with query results in body (like send_employee_count.py)
                logger.warning("[ORCHESTRATOR:EMAIL] No report path found - creating email from query results")

                # Extract query results from state
                query_result = state.get("query_result", {})
                # ChatbotTool wraps results: {"success": bool, "result": {actual_data}}
                tool_result = query_result.get("result", {})
                query_rows = tool_result.get("results", [])

                # Create HTML email body with query results
                from datetime import datetime
                current_date = datetime.now().strftime("%B %d, %Y at %I:%M %p")

                # Format query results as HTML table
                html_rows = ""
                if query_rows:
                    # Get column names from first row
                    columns = list(query_rows[0].keys()) if query_rows else []

                    # Create table headers
                    html_headers = "".join([f"<th style='padding: 10px; border: 1px solid #ddd; background: #667eea; color: white;'>{col}</th>" for col in columns])

                    # Create table rows
                    for row in query_rows[:10]:  # Limit to first 10 rows for email
                        html_cells = "".join([f"<td style='padding: 10px; border: 1px solid #ddd;'>{row.get(col, '')}</td>" for col in columns])
                        html_rows += f"<tr>{html_cells}</tr>"

                    table_html = f"""
                    <table style='border-collapse: collapse; width: 100%; margin: 20px 0;'>
                        <thead><tr>{html_headers}</tr></thead>
                        <tbody>{html_rows}</tbody>
                    </table>
                    """
                else:
                    table_html = "<p>No results to display.</p>"

                # Build complete HTML email body (similar to send_employee_count.py)
                body_html = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="UTF-8">
                    <style>
                        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; line-height: 1.6; color: #333; }}
                        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
                        .content {{ background: white; padding: 30px; border: 1px solid #e0e0e0; }}
                        .metadata {{ background: #f8f9fa; padding: 20px; border-radius: 8px; margin-top: 30px; font-size: 13px; color: #666; }}
                    </style>
                </head>
                <body>
                    <div class="header">
                        <h1>OryggiAI Database Query Results</h1>
                        <p>AI-Powered Database Assistant</p>
                    </div>
                    <div class="content">
                        <h2>{state['question']}</h2>
                        <p>Here are the results from your query:</p>
                        {table_html}
                        <div class="metadata">
                            <p><strong>Query:</strong> {tool_result.get('sql_query', 'N/A')}</p>
                            <p><strong>Rows Returned:</strong> {len(query_rows)}</p>
                            <p><strong>Generated:</strong> {current_date}</p>
                        </div>
                    </div>
                </body>
                </html>
                """
                attachment_path = None

            logger.info("[ORCHESTRATOR:EMAIL] Email parameters:")
            logger.info(f"[ORCHESTRATOR:EMAIL]   Recipient: {email_recipient}")
            logger.info(f"[ORCHESTRATOR:EMAIL]   Subject: {subject}")
            logger.info(f"[ORCHESTRATOR:EMAIL]   Body HTML length: {len(body_html)} chars")
            logger.info(f"[ORCHESTRATOR:EMAIL]   Attachment: {attachment_path if attachment_path else 'None (query results in body)'}")
            logger.info(f"[ORCHESTRATOR:EMAIL]   User ID: {state['user_id']}")
            logger.info(f"[ORCHESTRATOR:EMAIL]   User role: {state['user_role']}")

            # Send email (with or without attachment)
            logger.info("[ORCHESTRATOR:EMAIL] Calling send_email_tool.run()...")
            result = await send_email_tool.run(
                user_role=state["user_role"],
                recipient=email_recipient,
                subject=subject,
                body_html=body_html,
                attachment_path=attachment_path,
                user_id=state["user_id"]
            )

            logger.info(f"[ORCHESTRATOR:EMAIL] send_email_tool.run() returned: {result}")

            state["email_result"] = result
            state["tools_called"].append("send_email")

            if result.get("success"):
                logger.success("=" * 80)
                logger.success(f"[ORCHESTRATOR:EMAIL] EMAIL SENT SUCCESSFULLY to {email_recipient}")
                logger.success("=" * 80)
            else:
                logger.error("=" * 80)
                logger.error(f"[ORCHESTRATOR:EMAIL] EMAIL SENDING FAILED: {result.get('error')}")
                logger.error("=" * 80)

            logger.info("[ORCHESTRATOR:EMAIL] Returning state with email result")
            return state

        except Exception as e:
            logger.error("=" * 80)
            logger.error(f"[ORCHESTRATOR:EMAIL] EXCEPTION during email execution: {str(e)}")
            logger.error("=" * 80)
            logger.exception("[ORCHESTRATOR:EMAIL] Full exception traceback:")
            state["email_result"] = {"success": False, "error": str(e)}
            logger.info("[ORCHESTRATOR:EMAIL] Returning state with exception error")
            return state

    def _format_response(self, state: ChatbotState) -> ChatbotState:
        """
        Step 5: Format final response based on executed tools
        """
        logger.info(f"[ORCHESTRATOR] Formatting response (tools used: {state.get('tools_called', [])})")

        # Build response message
        response_parts = []

        # Query result (with null checking)
        query_result = state.get("query_result") or {}
        if query_result and query_result.get("success"):
            result_data = query_result.get("result", {})
            response_parts.append(result_data.get("natural_answer", "Query executed successfully."))
        elif query_result and query_result.get("error"):
            response_parts.append(f"Query error: {query_result.get('error')}")
            state["success"] = False
            state["error"] = query_result.get("error")

        # Report result (with null checking)
        report_result = state.get("report_result") or {}
        if report_result and report_result.get("success"):
            result_data = report_result.get("result", {})
            report_path = result_data.get("report_path")
            report_format = result_data.get("format", "EXCEL").upper()
            rows_count = result_data.get("rows_count", 0)
            response_parts.append(
                f"\n\n{report_format} report generated successfully with {rows_count} rows.\n"
                f"Report saved to: {report_path}"
            )
        elif report_result and report_result.get("error"):
            response_parts.append(f"\n\nReport generation failed: {report_result.get('error')}")

        # Email result (with null checking)
        email_result = state.get("email_result") or {}
        if email_result and email_result.get("success"):
            recipient = state.get("email_recipient")
            response_parts.append(f"\n\nReport successfully emailed to: {recipient}")
        elif email_result and email_result.get("error"):
            response_parts.append(f"\n\nEmail sending failed: {email_result.get('error')}")

        # Combine all parts
        state["answer"] = "".join(response_parts)

        # Set overall success flag
        if state.get("success") is None:
            state["success"] = True  # Default to success if no errors

        logger.success(f"[ORCHESTRATOR] Response formatted successfully")

        return state

    async def process(
        self,
        question: str,
        user_id: str,
        user_role: str,
        session_id: str
    ) -> Dict[str, Any]:
        """
        Main entry point: Process user request through LangGraph workflow

        Args:
            question: User's natural language request
            user_id: User identifier
            user_role: User's role (ADMIN, HR_MANAGER, etc.)
            session_id: Conversation session ID

        Returns:
            Dict with answer, tools used, and execution results
        """
        logger.info(f"[ORCHESTRATOR] Processing request: {question}")

        # Phase 5/6: FIRST check if this is a confirmation/rejection of a pending action
        # This must be checked BEFORE is_action_request() because "yes"/"no" won't match action keywords
        confirmation_words = ['yes', 'confirm', 'proceed', 'approve', 'ok', 'sure', 'go ahead', 'do it']
        rejection_words = ['no', 'cancel', 'reject', 'stop', 'abort', 'nevermind', 'never mind', "don't"]
        question_lower = question.lower().strip()

        is_confirmation = any(word in question_lower for word in confirmation_words)
        is_rejection = any(word in question_lower for word in rejection_words)

        if is_confirmation or is_rejection:
            # Check if there's a pending action for this session
            pending_actions = await pending_actions_store.get_pending_actions(
                session_id=session_id,
                status=ActionStatus.PENDING
            )

            if pending_actions:
                pending_action = pending_actions[0]  # Get the most recent pending action
                logger.info(f"[ORCHESTRATOR] Found pending action {pending_action.id} for session {session_id}")
                logger.info(f"[ORCHESTRATOR] User response: {'CONFIRM' if is_confirmation else 'REJECT'}")

                try:
                    # Route to action orchestrator with confirmation context
                    action_result = await action_orchestrator.process(
                        question=question,
                        user_id=user_id,
                        user_role=user_role,
                        session_id=session_id,
                        pending_action_id=pending_action.id,
                        is_confirmation=is_confirmation
                    )
                    logger.info(f"[ORCHESTRATOR] Action Orchestrator (confirmation) returned: success={action_result.get('success')}")
                    return {
                        "answer": action_result.get("answer", ""),
                        "success": action_result.get("success", True),
                        "error": action_result.get("error"),
                        "tools_called": action_result.get("tools_called", []),
                        "intent": "access_control_confirmation",
                        "action_type": action_result.get("action_type"),
                        "action_params": action_result.get("action_params"),
                        "awaiting_confirmation": False,
                        "confirmation_message": None,
                        "thread_id": action_result.get("thread_id"),
                        "query_result": None,
                        "report_result": None,
                        "email_result": None
                    }
                except Exception as e:
                    logger.error(f"[ORCHESTRATOR] Action confirmation failed: {str(e)}", exc_info=True)
                    return {
                        "answer": f"Error processing action confirmation: {str(e)}",
                        "success": False,
                        "error": str(e),
                        "tools_called": [],
                        "intent": "access_control_confirmation"
                    }

        # Phase 5/6: Check if this is an access control action request
        # Route to Action Orchestrator for grant, block, revoke, visitor registration, etc.
        if action_orchestrator.is_action_request(question):
            logger.info("[ORCHESTRATOR] Detected access control action request - routing to Action Orchestrator")
            try:
                action_result = await action_orchestrator.process(
                    question=question,
                    user_id=user_id,
                    user_role=user_role,
                    session_id=session_id
                )
                logger.info(f"[ORCHESTRATOR] Action Orchestrator returned: success={action_result.get('success')}")
                return {
                    "answer": action_result.get("answer", ""),
                    "success": action_result.get("success", True),
                    "error": action_result.get("error"),
                    "tools_called": action_result.get("tools_called", []),
                    "intent": "access_control_action",
                    "action_type": action_result.get("action_type"),
                    "action_params": action_result.get("action_params"),
                    "awaiting_confirmation": action_result.get("awaiting_confirmation", False),
                    "confirmation_message": action_result.get("confirmation_message"),
                    "thread_id": action_result.get("thread_id"),
                    "query_result": None,
                    "report_result": None,
                    "email_result": None
                }
            except Exception as e:
                logger.error(f"[ORCHESTRATOR] Action Orchestrator failed: {str(e)}", exc_info=True)
                return {
                    "answer": f"Error processing access control action: {str(e)}",
                    "success": False,
                    "error": str(e),
                    "tools_called": [],
                    "intent": "access_control_action"
                }

        # Initialize state (including clarity assessment fields)
        initial_state = {
            "question": question,
            "user_id": user_id,
            "user_role": user_role,
            "session_id": session_id,
            # Clarity assessment fields
            "is_clear": True,
            "clarity_confidence": 1.0,
            "needs_clarification": False,
            "clarification_question": None,
            "clarification_options": None,
            "clarification_attempt": 1,
            "max_clarification_attempts": 3,
            "original_question": None,
            # Intent classification
            "intent": None,
            "report_format": None,
            "email_recipient": None,
            "tools_called": [],
            "query_result": None,
            "report_result": None,
            "email_result": None,
            "answer": "",
            "success": True,
            "error": None,
            # PERFORMANCE: Initialize conversation_history cache
            "conversation_history": None
        }

        try:
            # Execute workflow (use async ainvoke for async nodes)
            final_state = await self.workflow.ainvoke(initial_state)

            logger.success(
                f"[ORCHESTRATOR] Workflow completed successfully. "
                f"Tools used: {final_state.get('tools_called', [])}"
            )

            return {
                "answer": final_state.get("answer", ""),
                "success": final_state.get("success", True),
                "error": final_state.get("error"),
                "tools_called": final_state.get("tools_called", []),
                "intent": final_state.get("intent"),
                "query_result": final_state.get("query_result"),
                "report_result": final_state.get("report_result"),
                "email_result": final_state.get("email_result"),
                # Clarification fields
                "needs_clarification": final_state.get("needs_clarification", False),
                "clarification_question": final_state.get("clarification_question"),
                "clarification_options": final_state.get("clarification_options"),
                "clarification_attempt": final_state.get("clarification_attempt", 1),
                "max_clarification_attempts": final_state.get("max_clarification_attempts", 3),
                "original_question": final_state.get("original_question")
            }

        except Exception as e:
            logger.error(f"[ORCHESTRATOR] Workflow execution failed: {str(e)}", exc_info=True)
            return {
                "answer": f"I encountered an error processing your request: {str(e)}",
                "success": False,
                "error": str(e),
                "tools_called": [],
                "intent": None
            }


# Global orchestrator instance
chatbot_orchestrator = ChatbotOrchestrator()
