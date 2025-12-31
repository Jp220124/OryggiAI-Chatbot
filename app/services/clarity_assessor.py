"""
Clarity Assessor Service
Detects unclear/ambiguous prompts and generates clarifying questions

This service uses a hybrid approach:
1. Fast heuristics for obvious unclear cases (no LLM call)
2. LLM-based assessment for nuanced cases
3. Smart question generation with selectable options
"""

import re
import json
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from loguru import logger
import google.generativeai as genai

from app.config import settings


class ClarityAssessment(BaseModel):
    """Result of clarity assessment"""
    is_clear: bool = Field(description="Whether the prompt is clear enough to process")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence score 0-1")
    reason: Optional[str] = Field(default=None, description="Reason for unclear assessment")
    missing_info: List[str] = Field(default_factory=list, description="What information is missing")
    possible_intents: List[str] = Field(default_factory=list, description="What the user might be asking")


class ClarificationQuestion(BaseModel):
    """Generated clarifying question with options"""
    question: str = Field(description="The clarifying question to ask")
    options: List[str] = Field(default_factory=list, description="Selectable options for user")
    context_hint: Optional[str] = Field(default=None, description="Additional context for the question")


class ClarificationState(BaseModel):
    """Track clarification state for a session"""
    original_question: str = Field(description="The original unclear question")
    clarification_attempt: int = Field(default=1, description="Current attempt number")
    max_attempts: int = Field(default=3, description="Maximum clarification attempts")
    questions_asked: List[str] = Field(default_factory=list, description="Questions already asked")
    user_responses: List[str] = Field(default_factory=list, description="User's responses to clarifications")
    is_resolved: bool = Field(default=False, description="Whether clarification is complete")


class ClarityAssessor:
    """
    Assesses prompt clarity and generates clarifying questions.

    Uses hybrid approach:
    - Fast heuristics for obvious cases (empty, too short, incomplete)
    - LLM for nuanced assessment and question generation
    """

    # Confidence threshold - below this, ask for clarification
    CLARITY_THRESHOLD = 0.7

    # Patterns that indicate incomplete sentences
    INCOMPLETE_ENDINGS = [
        'the', 'a', 'an', 'to', 'for', 'with', 'from', 'by', 'at', 'in', 'on',
        'and', 'or', 'but', 'of', 'about', 'like', 'as', 'into', 'through'
    ]

    # Ambiguous pronouns without clear referents
    AMBIGUOUS_PRONOUNS = ['it', 'that', 'this', 'them', 'they', 'he', 'she', 'him', 'her']

    # Very short queries that likely need clarification
    MIN_WORDS_FOR_CLARITY = 3

    # Greetings that are not actual queries
    GREETINGS = ['hi', 'hello', 'hey', 'hola', 'greetings', 'good morning', 'good afternoon',
                 'good evening', 'howdy', 'sup', 'yo', 'hii', 'hiii', 'heya', 'hiya']

    # CLEAR ACTION KEYWORDS - These indicate a clear, actionable request (BYPASS LLM)
    CLEAR_ACTION_KEYWORDS = [
        # Report generation
        'generate report', 'create report', 'excel report', 'pdf report', 'make report',
        'generate excel', 'create excel', 'download report', 'export report',
        # Query actions
        'how many', 'show me', 'list all', 'get all', 'find all', 'count',
        'show all', 'display all', 'fetch all', 'retrieve all',
        # Employee queries
        'employees', 'employee count', 'active employees', 'total employees',
        'all employees', 'employee list', 'staff list', 'employee report',
        # Department queries
        'departments', 'department list', 'by department', 'per department',
        # Attendance queries
        'attendance', 'late arrivals', 'who was late', 'present today', 'absent today',
        # Email actions
        'email report', 'send report', 'email me', 'send me',
        # Access control
        'grant access', 'revoke access', 'block access', 'give access',
    ]

    # CLEAR PATTERN REGEX - Requests matching these are ALWAYS clear
    CLEAR_PATTERNS = [
        r'(generate|create|make|download|export)\s+(an?\s+)?(excel|pdf|csv)?\s*report',
        r'(show|list|get|find|display|fetch)\s+(me\s+)?(all|the|every)\s+\w+',
        r'how\s+many\s+\w+',
        r'(total|count|number\s+of)\s+\w+',
        r'(email|send)\s+(me\s+)?(a|an|the)?\s*(report|list|data)',
        r'(grant|revoke|block|give)\s+\w*\s*access',
        r'who\s+(is|was|are|were)\s+(late|absent|present)',
    ]

    def __init__(self):
        """Initialize with Gemini model"""
        genai.configure(api_key=settings.gemini_api_key)
        self.model = genai.GenerativeModel(settings.gemini_model)
        logger.info("[CLARITY] ClarityAssessor initialized")

    def _check_heuristics(self, question: str) -> Optional[ClarityAssessment]:
        """
        Fast heuristic checks for obvious clear AND unclear cases.
        Returns ClarityAssessment if determination can be made, None if needs LLM check.
        """
        question = question.strip()

        # Check 0: Empty or whitespace only
        if not question:
            return ClarityAssessment(
                is_clear=False,
                confidence=0.0,
                reason="empty_input",
                missing_info=["No question provided"],
                possible_intents=[]
            )

        question_lower = question.lower()

        # =====================================================
        # CLEAR PATTERNS CHECK (NEW - BYPASS LLM FOR CLEAR REQUESTS)
        # =====================================================
        # Check for clear action keywords FIRST - these are obviously actionable
        for keyword in self.CLEAR_ACTION_KEYWORDS:
            if keyword in question_lower:
                logger.info(f"[CLARITY] CLEAR: Matched keyword '{keyword}' - bypassing LLM")
                return ClarityAssessment(
                    is_clear=True,
                    confidence=0.95,
                    reason="clear_action_keyword",
                    missing_info=[],
                    possible_intents=[]
                )

        # Check for clear regex patterns
        for pattern in self.CLEAR_PATTERNS:
            if re.search(pattern, question_lower):
                logger.info(f"[CLARITY] CLEAR: Matched pattern '{pattern}' - bypassing LLM")
                return ClarityAssessment(
                    is_clear=True,
                    confidence=0.95,
                    reason="clear_pattern_match",
                    missing_info=[],
                    possible_intents=[]
                )

        # Check if question has enough content to be clear (5+ words with action verb)
        words = question.split()
        action_verbs = ['show', 'list', 'get', 'find', 'generate', 'create', 'count',
                        'how', 'what', 'who', 'display', 'email', 'send', 'export']
        has_action = any(word.lower() in action_verbs for word in words[:3])
        if len(words) >= 5 and has_action:
            logger.info(f"[CLARITY] CLEAR: Long query with action verb - bypassing LLM")
            return ClarityAssessment(
                is_clear=True,
                confidence=0.85,
                reason="actionable_query",
                missing_info=[],
                possible_intents=[]
            )

        # =====================================================
        # UNCLEAR PATTERNS CHECK (Original logic)
        # =====================================================

        # Check 2: Greeting detection (hi, hello, hey, etc.)
        greeting_check = question_lower.strip('!?.,:;')
        if greeting_check in self.GREETINGS or greeting_check.split()[0] in self.GREETINGS:
            return ClarityAssessment(
                is_clear=False,
                confidence=0.1,
                reason="greeting",
                missing_info=["This looks like a greeting, not a database query"],
                possible_intents=["User might want to start a conversation"]
            )

        # Check 3: Too short (single word or two words)
        words = question.split()
        if len(words) < self.MIN_WORDS_FOR_CLARITY:
            return ClarityAssessment(
                is_clear=False,
                confidence=0.3,
                reason="too_short",
                missing_info=["Query is too brief - need more context"],
                possible_intents=[f"Something related to '{question}'"]
            )

        # Check 3: Ends with incomplete word (preposition, article)
        last_word = words[-1].lower().rstrip('?.,!')
        if last_word in self.INCOMPLETE_ENDINGS:
            return ClarityAssessment(
                is_clear=False,
                confidence=0.2,
                reason="incomplete_sentence",
                missing_info=["Sentence appears incomplete"],
                possible_intents=[]
            )

        # Check 4: Only contains pronouns without context
        content_words = [w.lower() for w in words if w.lower() not in ['the', 'a', 'an', 'please', 'can', 'you', 'i', 'me', 'my']]
        if all(w in self.AMBIGUOUS_PRONOUNS for w in content_words) and len(content_words) > 0:
            return ClarityAssessment(
                is_clear=False,
                confidence=0.2,
                reason="ambiguous_reference",
                missing_info=["Unclear what 'it/that/this' refers to"],
                possible_intents=[]
            )

        # Check 5: Common unclear patterns
        unclear_patterns = [
            (r'^(show|get|give|send|do)\s+(it|that|this)$', "ambiguous_reference"),
            (r'^(what|how)\s+(about|if)$', "incomplete_question"),
            (r'^(yes|no|ok|okay|sure)$', "confirmation_without_context"),
        ]

        for pattern, reason in unclear_patterns:
            if re.match(pattern, question.lower()):
                return ClarityAssessment(
                    is_clear=False,
                    confidence=0.2,
                    reason=reason,
                    missing_info=["Need more specific information"],
                    possible_intents=[]
                )

        # Heuristics passed - needs LLM assessment
        return None

    async def assess_clarity(
        self,
        question: str,
        conversation_history: List[Dict] = None,
        session_context: Dict = None
    ) -> ClarityAssessment:
        """
        Assess if a user's prompt is clear enough to process.

        Args:
            question: The user's input
            conversation_history: Previous messages for context
            session_context: Additional session context

        Returns:
            ClarityAssessment with clarity score and details
        """
        logger.info(f"[CLARITY] Assessing clarity for: '{question}'")

        # Step 1: Fast heuristic check
        heuristic_result = self._check_heuristics(question)
        if heuristic_result is not None:
            logger.info(f"[CLARITY] Heuristic result: is_clear={heuristic_result.is_clear}, reason={heuristic_result.reason}")
            return heuristic_result

        # Step 2: LLM-based assessment for nuanced cases
        try:
            assessment = await self._llm_assess_clarity(question, conversation_history)
            logger.info(f"[CLARITY] LLM result: is_clear={assessment.is_clear}, confidence={assessment.confidence}")
            return assessment
        except Exception as e:
            logger.error(f"[CLARITY] LLM assessment failed: {e}")
            # Fallback: assume clear if LLM fails (don't block user)
            return ClarityAssessment(
                is_clear=True,
                confidence=0.5,
                reason="llm_fallback",
                missing_info=[],
                possible_intents=[]
            )

    async def _llm_assess_clarity(
        self,
        question: str,
        conversation_history: List[Dict] = None
    ) -> ClarityAssessment:
        """Use LLM to assess prompt clarity"""

        # Build context from conversation history
        context_str = ""
        if conversation_history:
            recent = conversation_history[-5:]  # Last 5 messages
            context_str = "\n".join([
                f"- {msg.get('role', 'user')}: {msg.get('content', '')[:100]}"
                for msg in recent
            ])
            context_str = f"\nRECENT CONVERSATION:\n{context_str}\n"

        prompt = f"""Analyze this user query for clarity and completeness.

USER QUERY: "{question}"
{context_str}
CONTEXT: This is an enterprise database chatbot that can:
- Query employee/HR data from SQL database
- Generate Excel reports
- Send emails with data/reports
- Manage access control (grant/revoke permissions)

ASSESSMENT TASK:
Determine if this query is clear and specific enough to execute.

A query is UNCLEAR if:
- It's missing WHO (which employee, department, etc.)
- It's missing WHAT (what data, what action)
- It's missing WHEN (time period, dates)
- It uses pronouns without clear references ("it", "that", "them")
- It's ambiguous and could mean multiple different things
- It's a fragment or incomplete thought

A query is CLEAR if:
- The intent is obvious (even if brief, like "employee count")
- It specifies what data/action is needed
- Context from conversation makes it clear

Return ONLY valid JSON (no markdown):
{{
  "is_clear": true/false,
  "confidence": 0.0-1.0,
  "reason": "brief explanation if unclear",
  "missing_info": ["list", "of", "missing", "details"],
  "possible_intents": ["what user might want 1", "what user might want 2"]
}}"""

        response = self.model.generate_content(prompt)
        result_text = response.text.strip()

        # Clean up response
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0].strip()
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0].strip()

        result = json.loads(result_text)

        # Apply threshold
        is_clear = result.get("is_clear", True) and result.get("confidence", 1.0) >= self.CLARITY_THRESHOLD

        return ClarityAssessment(
            is_clear=is_clear,
            confidence=result.get("confidence", 1.0),
            reason=result.get("reason"),
            missing_info=result.get("missing_info", []),
            possible_intents=result.get("possible_intents", [])
        )

    async def generate_clarifying_question(
        self,
        question: str,
        assessment: ClarityAssessment,
        previous_clarifications: List[str] = None
    ) -> ClarificationQuestion:
        """
        Generate a clarifying question with selectable options.

        Args:
            question: Original unclear question
            assessment: The clarity assessment result
            previous_clarifications: Questions already asked (to avoid repetition)

        Returns:
            ClarificationQuestion with question and options
        """
        logger.info(f"[CLARITY] Generating clarifying question for: '{question}'")

        # Build exclusion list
        exclude_str = ""
        if previous_clarifications:
            exclude_str = f"\nDO NOT ask these questions again (already asked):\n" + \
                         "\n".join([f"- {q}" for q in previous_clarifications])

        prompt = f"""Generate a helpful clarifying question for this unclear user input.

USER INPUT: "{question}"

WHY IT'S UNCLEAR:
- Reason: {assessment.reason or 'ambiguous'}
- Missing: {', '.join(assessment.missing_info) if assessment.missing_info else 'specific details'}
- Possible intents: {', '.join(assessment.possible_intents) if assessment.possible_intents else 'unknown'}
{exclude_str}

CONTEXT: Enterprise database chatbot for employee/HR data, reports, emails, and access control.

REQUIREMENTS:
1. Ask ONE clear, friendly question
2. Provide 3-4 SPECIFIC options the user can choose from
3. Options should be actionable queries the system can actually execute
4. Keep the question concise and helpful
5. Don't be condescending - be professional

Return ONLY valid JSON (no markdown):
{{
  "question": "Your clarifying question here?",
  "options": [
    "Specific actionable option 1",
    "Specific actionable option 2",
    "Specific actionable option 3",
    "Specific actionable option 4"
  ],
  "context_hint": "Optional brief hint about what info would help"
}}"""

        try:
            response = self.model.generate_content(prompt)
            result_text = response.text.strip()

            # Clean up response
            if "```json" in result_text:
                result_text = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                result_text = result_text.split("```")[1].split("```")[0].strip()

            result = json.loads(result_text)

            return ClarificationQuestion(
                question=result.get("question", "Could you please provide more details?"),
                options=result.get("options", [])[:4],  # Max 4 options
                context_hint=result.get("context_hint")
            )

        except Exception as e:
            logger.error(f"[CLARITY] Question generation failed: {e}")
            # Fallback generic question
            return self._generate_fallback_question(question, assessment)

    def _generate_fallback_question(
        self,
        question: str,
        assessment: ClarityAssessment
    ) -> ClarificationQuestion:
        """Generate a fallback question if LLM fails"""

        # Based on the reason, generate appropriate fallback
        if assessment.reason == "empty_input":
            return ClarificationQuestion(
                question="What would you like to know or do?",
                options=[
                    "How many total employees are there?",
                    "Show me recent hires from last 30 days",
                    "Generate an employee report",
                    "List all departments"
                ]
            )

        if assessment.reason == "greeting":
            return ClarificationQuestion(
                question="Hello! I'm your database assistant. How can I help you today?",
                options=[
                    "How many employees are in the database?",
                    "Show me the top 5 departments by size",
                    "Generate an Excel report of employees",
                    "List employees who joined recently"
                ],
                context_hint="I can help you query employee data, generate reports, and more."
            )

        if assessment.reason == "too_short":
            # Don't just substitute the word - provide smart database-relevant options
            return ClarificationQuestion(
                question="I'd like to help! Could you tell me more about what you're looking for?",
                options=[
                    "Show total employee count",
                    "List employees by department",
                    "Show recent hires",
                    "Generate a report"
                ],
                context_hint="Try asking something like 'How many employees are in IT department?'"
            )

        if assessment.reason == "incomplete_sentence":
            return ClarificationQuestion(
                question="It looks like your message was cut off. What would you like to see?",
                options=[
                    "How many total employees are there?",
                    "Show me the top 10 departments by employee count",
                    "List employees who joined in the last 30 days",
                    "Generate an Excel report of all employees"
                ]
            )

        if assessment.reason == "ambiguous_reference":
            return ClarificationQuestion(
                question="I'm not sure what you're referring to. Could you be more specific?",
                options=[
                    "Show me the total employee count",
                    "List all departments with employee counts",
                    "Show employees in a specific department",
                    "Generate a summary report"
                ]
            )

        # Generic fallback
        return ClarificationQuestion(
            question="Could you please provide more details about what you need?",
            options=[
                "How many employees are in the database?",
                "Show me employees grouped by department",
                "List recent hires from last 30 days",
                "Generate an Excel report of employees"
            ]
        )

    def combine_with_clarification(
        self,
        original_question: str,
        clarification_response: str,
        clarification_question: str
    ) -> str:
        """
        Combine original question with user's clarification response
        to create an enriched, clear question.

        Args:
            original_question: The original unclear question
            clarification_response: User's response to clarification
            clarification_question: The question that was asked

        Returns:
            Combined clear question
        """
        # If user selected an option, use it directly
        if clarification_response and len(clarification_response) > 3:
            # Check if it's a complete sentence/query
            if any(word in clarification_response.lower() for word in ['show', 'list', 'get', 'count', 'generate', 'send', 'how many']):
                return clarification_response

        # Combine original with clarification
        combined = f"{original_question}. Specifically: {clarification_response}"
        return combined


# Global instance
clarity_assessor = ClarityAssessor()
