"""
Actions API Endpoints
Handles action confirmation workflow for Human-in-the-Loop
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from loguru import logger
import time

from app.services.pending_actions_store import (
    pending_actions_store,
    ActionStatus
)
from app.workflows.action_orchestrator import action_orchestrator
from app.middleware.audit_logger import audit_logger


# Create router
router = APIRouter()


# ============================================================================
# Request/Response Models
# ============================================================================

class ActionRequest(BaseModel):
    """Request to execute an access control action"""
    question: str = Field(..., description="User's action request in natural language")
    user_id: str = Field(..., description="User ID")
    user_role: str = Field(..., description="User's role (ADMIN, HR_MANAGER, etc.)")
    session_id: str = Field(..., description="Chat session ID")

    model_config = {"extra": "forbid"}


class ActionResponse(BaseModel):
    """Response from action execution"""
    success: bool
    answer: str
    action_type: Optional[str] = None
    awaiting_confirmation: bool = False
    confirmation_message: Optional[str] = None
    thread_id: Optional[str] = None
    error: Optional[str] = None
    tools_called: List[str] = []

    model_config = {"extra": "ignore"}


class PendingActionResponse(BaseModel):
    """Representation of a pending action"""
    id: str
    session_id: str
    user_id: str
    user_role: str
    action_type: str
    tool_name: str
    action_params: Dict[str, Any]
    confirmation_message: str
    status: str
    created_at: str
    expires_at: str
    langgraph_thread_id: Optional[str] = None

    model_config = {"extra": "ignore"}


class ConfirmActionRequest(BaseModel):
    """Request to confirm or reject an action"""
    user_id: str = Field(..., description="User confirming/rejecting")
    reason: Optional[str] = Field(None, description="Reason for rejection (if rejected)")

    model_config = {"extra": "forbid"}


class ConfirmActionResponse(BaseModel):
    """Response after confirming/rejecting an action"""
    success: bool
    action_id: str
    status: str
    message: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    model_config = {"extra": "ignore"}


# ============================================================================
# API Endpoints
# ============================================================================

@router.post("/execute", response_model=ActionResponse)
async def execute_action(request: ActionRequest):
    """
    Execute an access control action

    This endpoint processes action requests (grant, block, revoke access).
    If the action requires confirmation, it returns awaiting_confirmation=True
    and the thread_id needed to confirm later.

    **Flow:**
    1. User sends action request
    2. If action requires confirmation:
       - Returns confirmation_message and thread_id
       - Frontend shows confirmation dialog
       - User calls /actions/{thread_id}/approve or /reject
    3. If action doesn't need confirmation (e.g., list_access):
       - Executes immediately and returns result

    **Example Request (Destructive Action):**
    ```json
    {
        "question": "Grant user EMP001 access to Server Room",
        "user_id": "admin_001",
        "user_role": "ADMIN",
        "session_id": "sess_123"
    }
    ```

    **Example Response (Awaiting Confirmation):**
    ```json
    {
        "success": true,
        "answer": "Grant access for user EMP001 to Server Room?...",
        "action_type": "grant_access",
        "awaiting_confirmation": true,
        "confirmation_message": "Grant access for user EMP001...",
        "thread_id": "sess_123"
    }
    ```
    """
    start_time = time.time()

    logger.info(f"[ACTIONS_API] Execute action request: {request.question}")
    logger.info(f"[ACTIONS_API] User: {request.user_id} ({request.user_role})")

    try:
        # Process using action orchestrator
        result = await action_orchestrator.process(
            question=request.question,
            user_id=request.user_id,
            user_role=request.user_role,
            session_id=request.session_id
        )

        execution_time = time.time() - start_time
        logger.info(f"[ACTIONS_API] Action processed in {execution_time:.2f}s")

        # If awaiting confirmation, store pending action
        if result.get("awaiting_confirmation"):
            # Store pending action for tracking
            action = await pending_actions_store.create_pending_action(
                session_id=request.session_id,
                user_id=request.user_id,
                user_role=request.user_role,
                action_type=result.get("action_type", "unknown"),
                tool_name=result.get("action_type", "unknown"),
                action_params=result.get("action_params", {}),
                confirmation_message=result.get("confirmation_message", ""),
                langgraph_thread_id=result.get("thread_id")
            )
            logger.info(f"[ACTIONS_API] Created pending action: {action.id}")

        return ActionResponse(
            success=result.get("success", True),
            answer=result.get("answer", ""),
            action_type=result.get("action_type"),
            awaiting_confirmation=result.get("awaiting_confirmation", False),
            confirmation_message=result.get("confirmation_message"),
            thread_id=result.get("thread_id"),
            error=result.get("error"),
            tools_called=result.get("tools_called", [])
        )

    except Exception as e:
        logger.error(f"[ACTIONS_API] Action execution failed: {str(e)}", exc_info=True)
        return ActionResponse(
            success=False,
            answer=f"Failed to process action: {str(e)}",
            error=str(e),
            awaiting_confirmation=False
        )


@router.get("/pending", response_model=List[PendingActionResponse])
async def list_pending_actions(
    session_id: Optional[str] = None,
    user_id: Optional[str] = None
):
    """
    List pending actions awaiting confirmation

    **Query Parameters:**
    - session_id: Filter by session (optional)
    - user_id: Filter by user (optional)

    **Example Response:**
    ```json
    [
        {
            "id": "uuid-123",
            "session_id": "sess_123",
            "user_id": "admin_001",
            "user_role": "ADMIN",
            "action_type": "grant_access",
            "tool_name": "grant_access",
            "action_params": {"target_user_id": "EMP001", ...},
            "confirmation_message": "Grant access for user EMP001...",
            "status": "pending",
            "created_at": "2025-01-22T10:30:00Z",
            "expires_at": "2025-01-22T10:35:00Z",
            "langgraph_thread_id": "sess_123"
        }
    ]
    ```
    """
    logger.info(f"[ACTIONS_API] Listing pending actions (session={session_id}, user={user_id})")

    try:
        actions = await pending_actions_store.get_pending_actions(
            session_id=session_id,
            user_id=user_id,
            status=ActionStatus.PENDING
        )

        return [
            PendingActionResponse(
                id=a.id,
                session_id=a.session_id,
                user_id=a.user_id,
                user_role=a.user_role,
                action_type=a.action_type,
                tool_name=a.tool_name,
                action_params=a.action_params,
                confirmation_message=a.confirmation_message,
                status=a.status.value,
                created_at=a.created_at.isoformat(),
                expires_at=a.expires_at.isoformat(),
                langgraph_thread_id=a.langgraph_thread_id
            )
            for a in actions
        ]

    except Exception as e:
        logger.error(f"[ACTIONS_API] Failed to list pending actions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pending/{action_id}", response_model=PendingActionResponse)
async def get_pending_action(action_id: str):
    """
    Get a specific pending action by ID

    **Path Parameters:**
    - action_id: UUID of the pending action
    """
    logger.info(f"[ACTIONS_API] Getting pending action: {action_id}")

    try:
        action = await pending_actions_store.get_pending_action(action_id)

        if not action:
            raise HTTPException(status_code=404, detail="Action not found")

        return PendingActionResponse(
            id=action.id,
            session_id=action.session_id,
            user_id=action.user_id,
            user_role=action.user_role,
            action_type=action.action_type,
            tool_name=action.tool_name,
            action_params=action.action_params,
            confirmation_message=action.confirmation_message,
            status=action.status.value,
            created_at=action.created_at.isoformat(),
            expires_at=action.expires_at.isoformat(),
            langgraph_thread_id=action.langgraph_thread_id
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[ACTIONS_API] Failed to get action: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{thread_id}/approve", response_model=ConfirmActionResponse)
async def approve_action(thread_id: str, request: ConfirmActionRequest):
    """
    Approve a pending action and execute it

    This resumes the LangGraph workflow with user confirmation,
    executes the action, and returns the result.

    **Path Parameters:**
    - thread_id: The LangGraph thread ID returned from /execute

    **Example Request:**
    ```json
    {
        "user_id": "admin_001"
    }
    ```

    **Example Response:**
    ```json
    {
        "success": true,
        "action_id": "thread_123",
        "status": "executed",
        "message": "Access granted successfully.",
        "result": {
            "permission_id": "PERM-ABC123",
            "target_name": "Server Room"
        }
    }
    ```
    """
    logger.info(f"[ACTIONS_API] Approving action: {thread_id}")

    try:
        # First, try to get the pending action by ID (UUID)
        pending_action = await pending_actions_store.get_pending_action(thread_id)

        # If not found by ID, search by langgraph_thread_id
        if not pending_action:
            actions = await pending_actions_store.get_pending_actions(status=ActionStatus.PENDING)
            for action in actions:
                if action.langgraph_thread_id == thread_id or action.id == thread_id:
                    pending_action = action
                    break

        if not pending_action:
            return ConfirmActionResponse(
                success=False,
                action_id=thread_id,
                status="not_found",
                message="Pending action not found",
                error="Action not found"
            )

        logger.info(f"[ACTIONS_API] Found action: {pending_action.id}, type={pending_action.action_type}")

        # Resume workflow with confirmation - pass all the action data
        result = await action_orchestrator.resume_with_confirmation(
            thread_id=pending_action.langgraph_thread_id or pending_action.id,
            confirmed=True,
            reason=None,
            action_type=pending_action.action_type,
            action_params=pending_action.action_params,
            user_id=pending_action.user_id,
            user_role=pending_action.user_role
        )

        # Update pending action status
        if result.get("success"):
            await pending_actions_store.mark_executed(pending_action.id, success=True)
        else:
            await pending_actions_store.mark_executed(
                pending_action.id,
                success=False,
                resolution_note=result.get("error")
            )

        # Log approval
        audit_logger.log_action_confirmation(
            user_id=request.user_id,
            user_role=pending_action.user_role,
            pending_action_id=pending_action.id,
            approved=True
        )

        return ConfirmActionResponse(
            success=result.get("success", False),
            action_id=pending_action.id,
            status="executed" if result.get("success") else "failed",
            message=result.get("answer", "Action completed"),
            result=result.get("action_result"),
            error=result.get("error")
        )

    except Exception as e:
        logger.error(f"[ACTIONS_API] Failed to approve action: {str(e)}", exc_info=True)
        return ConfirmActionResponse(
            success=False,
            action_id=thread_id,
            status="failed",
            message=f"Failed to execute action: {str(e)}",
            error=str(e)
        )


@router.post("/{thread_id}/reject", response_model=ConfirmActionResponse)
async def reject_action(thread_id: str, request: ConfirmActionRequest):
    """
    Reject a pending action

    This cancels the action and does not execute it.

    **Path Parameters:**
    - thread_id: The LangGraph thread ID returned from /execute

    **Example Request:**
    ```json
    {
        "user_id": "admin_001",
        "reason": "Request denied per company policy"
    }
    ```

    **Example Response:**
    ```json
    {
        "success": true,
        "action_id": "thread_123",
        "status": "rejected",
        "message": "Action cancelled by user"
    }
    ```
    """
    logger.info(f"[ACTIONS_API] Rejecting action: {thread_id}, reason: {request.reason}")

    try:
        # Resume workflow with rejection
        result = await action_orchestrator.resume_with_confirmation(
            thread_id=thread_id,
            confirmed=False,
            reason=request.reason
        )

        # Find and update pending action status
        actions = await pending_actions_store.get_pending_actions(status=ActionStatus.PENDING)
        for action in actions:
            if action.langgraph_thread_id == thread_id:
                await pending_actions_store.reject_action(
                    action.id,
                    rejected_by=request.user_id,
                    resolution_note=request.reason
                )
                break

        # Log rejection
        audit_logger.log_action_confirmation(
            user_id=request.user_id,
            user_role="ADMIN",  # TODO: Get actual role
            pending_action_id=thread_id,
            approved=False,
            resolution_note=request.reason
        )

        return ConfirmActionResponse(
            success=True,
            action_id=thread_id,
            status="rejected",
            message=result.get("answer", "Action cancelled by user")
        )

    except Exception as e:
        logger.error(f"[ACTIONS_API] Failed to reject action: {str(e)}", exc_info=True)
        return ConfirmActionResponse(
            success=False,
            action_id=thread_id,
            status="error",
            message=f"Failed to reject action: {str(e)}",
            error=str(e)
        )


@router.delete("/pending/expired")
async def cleanup_expired_actions():
    """
    Clean up expired pending actions

    Marks all expired pending actions as expired.
    This can be called periodically or on-demand.

    **Example Response:**
    ```json
    {
        "success": true,
        "expired_count": 5,
        "message": "Cleaned up 5 expired actions"
    }
    ```
    """
    logger.info("[ACTIONS_API] Cleaning up expired actions")

    try:
        count = await pending_actions_store.cleanup_expired()

        return {
            "success": True,
            "expired_count": count,
            "message": f"Cleaned up {count} expired actions"
        }

    except Exception as e:
        logger.error(f"[ACTIONS_API] Failed to cleanup expired actions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
