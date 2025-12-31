"""
Clarification Models
Pydantic models for tracking clarification state and responses
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class ClarificationStatus(str, Enum):
    """Status of a clarification request"""
    PENDING = "pending"          # Waiting for user response
    RESOLVED = "resolved"        # User provided clarification
    ABANDONED = "abandoned"      # User moved on without clarifying
    MAX_ATTEMPTS = "max_attempts"  # Hit max clarification attempts


class ClarificationRequest(BaseModel):
    """A single clarification request"""
    question: str = Field(description="The clarifying question asked")
    options: List[str] = Field(default_factory=list, description="Options provided to user")
    asked_at: datetime = Field(default_factory=datetime.utcnow)
    response: Optional[str] = Field(default=None, description="User's response")
    responded_at: Optional[datetime] = Field(default=None)


class SessionClarificationState(BaseModel):
    """
    Tracks clarification state for a user session.
    Stored in conversation memory to maintain context.
    """
    session_id: str = Field(description="Session ID this state belongs to")
    original_question: str = Field(description="The original unclear question")
    status: ClarificationStatus = Field(default=ClarificationStatus.PENDING)

    # Attempt tracking
    current_attempt: int = Field(default=1)
    max_attempts: int = Field(default=3)

    # History of clarification requests
    clarification_history: List[ClarificationRequest] = Field(default_factory=list)

    # Final resolved question (after clarification)
    resolved_question: Optional[str] = Field(default=None)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def add_clarification(self, question: str, options: List[str]) -> None:
        """Add a new clarification request"""
        self.clarification_history.append(
            ClarificationRequest(question=question, options=options)
        )
        self.updated_at = datetime.utcnow()

    def record_response(self, response: str) -> None:
        """Record user's response to latest clarification"""
        if self.clarification_history:
            self.clarification_history[-1].response = response
            self.clarification_history[-1].responded_at = datetime.utcnow()
        self.current_attempt += 1
        self.updated_at = datetime.utcnow()

    def is_max_attempts_reached(self) -> bool:
        """Check if max clarification attempts reached"""
        return self.current_attempt > self.max_attempts

    def get_asked_questions(self) -> List[str]:
        """Get list of questions already asked"""
        return [c.question for c in self.clarification_history]

    def resolve(self, final_question: str) -> None:
        """Mark clarification as resolved"""
        self.status = ClarificationStatus.RESOLVED
        self.resolved_question = final_question
        self.updated_at = datetime.utcnow()

    def abandon(self) -> None:
        """Mark clarification as abandoned"""
        self.status = ClarificationStatus.ABANDONED
        self.updated_at = datetime.utcnow()


class ClarificationResponse(BaseModel):
    """
    API response when clarification is needed.
    Returned to frontend when the chatbot needs more information.
    """
    needs_clarification: bool = Field(default=True)
    clarification_question: str = Field(description="Question to ask the user")
    clarification_options: List[str] = Field(default_factory=list, description="Selectable options")
    clarification_attempt: int = Field(default=1, description="Current attempt number")
    max_attempts: int = Field(default=3, description="Maximum attempts allowed")
    original_question: str = Field(description="The original unclear question")
    context_hint: Optional[str] = Field(default=None, description="Hint for the user")

    # Session tracking
    session_id: str = Field(description="Session ID for tracking")
    clarification_id: Optional[str] = Field(default=None, description="Unique ID for this clarification")


class UserClarificationInput(BaseModel):
    """
    User's response to a clarification request.
    Sent from frontend when user answers a clarifying question.
    """
    session_id: str = Field(description="Session ID")
    original_question: str = Field(description="The original question that needed clarification")
    clarification_response: str = Field(description="User's response/selection")
    selected_option_index: Optional[int] = Field(default=None, description="Index of selected option (if any)")
