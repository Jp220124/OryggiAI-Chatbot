"""
Pending Actions Store
Manages storage and retrieval of actions awaiting user confirmation
Integrates with PostgreSQL for persistence
"""

from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import uuid
import json
from loguru import logger

# Try PostgreSQL, fallback to in-memory
try:
    import asyncpg
    HAS_ASYNCPG = True
except ImportError:
    asyncpg = None  # type: ignore
    HAS_ASYNCPG = False
    logger.warning("asyncpg not installed, using in-memory pending actions store")


class ActionStatus(str, Enum):
    """Status of a pending action"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    EXECUTED = "executed"
    FAILED = "failed"


@dataclass
class PendingAction:
    """Represents an action awaiting user confirmation"""
    id: str
    session_id: str
    user_id: str
    user_role: str
    action_type: str  # grant_access, block_access, revoke_access
    tool_name: str
    action_params: Dict[str, Any]
    confirmation_message: str
    status: ActionStatus
    created_at: datetime
    expires_at: datetime
    langgraph_thread_id: Optional[str] = None
    langgraph_checkpoint_id: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolution_note: Optional[str] = None

    def is_expired(self) -> bool:
        """Check if action has expired"""
        return datetime.utcnow() > self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "user_role": self.user_role,
            "action_type": self.action_type,
            "tool_name": self.tool_name,
            "action_params": self.action_params,
            "confirmation_message": self.confirmation_message,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "langgraph_thread_id": self.langgraph_thread_id,
            "langgraph_checkpoint_id": self.langgraph_checkpoint_id,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolution_note": self.resolution_note
        }


class PendingActionsStore:
    """
    Store for managing pending actions that require user confirmation

    Supports both PostgreSQL (production) and in-memory (development) storage.

    Example:
        store = PendingActionsStore()

        # Create pending action
        action = await store.create_pending_action(
            session_id="sess_123",
            user_id="admin_001",
            user_role="ADMIN",
            action_type="grant_access",
            tool_name="grant_access",
            action_params={"target_user_id": "EMP001", ...},
            confirmation_message="Grant access to Server Room?"
        )

        # Approve action
        action = await store.approve_action(action.id, "admin_001")

        # Get pending actions for session
        actions = await store.get_pending_actions(session_id="sess_123")
    """

    def __init__(self, database_url: Optional[str] = None):
        """
        Initialize pending actions store

        Args:
            database_url: PostgreSQL connection URL (optional, falls back to in-memory)
        """
        self.database_url = database_url
        self._pool: Any = None  # asyncpg.Pool when available

        # In-memory fallback storage
        self._memory_store: Dict[str, PendingAction] = {}

        # Default expiration time (5 minutes)
        self.default_expiration_minutes = 5

        logger.info(f"PendingActionsStore initialized (PostgreSQL: {bool(database_url and HAS_ASYNCPG)})")

    async def _get_pool(self) -> Any:
        """Get or create database connection pool"""
        if not HAS_ASYNCPG or not self.database_url:
            return None

        if self._pool is None:
            try:
                self._pool = await asyncpg.create_pool(self.database_url)
                logger.info("PostgreSQL connection pool created for pending actions")
            except Exception as e:
                logger.error(f"Failed to create PostgreSQL pool: {e}")
                return None

        return self._pool

    async def create_pending_action(
        self,
        session_id: str,
        user_id: str,
        user_role: str,
        action_type: str,
        tool_name: str,
        action_params: Dict[str, Any],
        confirmation_message: str,
        langgraph_thread_id: Optional[str] = None,
        langgraph_checkpoint_id: Optional[str] = None,
        expiration_minutes: Optional[int] = None
    ) -> PendingAction:
        """
        Create a new pending action

        Args:
            session_id: Chat session ID
            user_id: User requesting the action
            user_role: User's role
            action_type: Type of action (grant_access, block_access, etc.)
            tool_name: Name of the tool to execute
            action_params: Parameters for the tool
            confirmation_message: Message to show user
            langgraph_thread_id: LangGraph thread ID for resumption
            langgraph_checkpoint_id: LangGraph checkpoint ID
            expiration_minutes: Minutes until action expires

        Returns:
            Created PendingAction
        """
        action_id = str(uuid.uuid4())
        now = datetime.utcnow()
        expires_at = now + timedelta(minutes=expiration_minutes or self.default_expiration_minutes)

        action = PendingAction(
            id=action_id,
            session_id=session_id,
            user_id=user_id,
            user_role=user_role,
            action_type=action_type,
            tool_name=tool_name,
            action_params=action_params,
            confirmation_message=confirmation_message,
            status=ActionStatus.PENDING,
            created_at=now,
            expires_at=expires_at,
            langgraph_thread_id=langgraph_thread_id,
            langgraph_checkpoint_id=langgraph_checkpoint_id
        )

        pool = await self._get_pool()

        if pool:
            # PostgreSQL storage
            try:
                async with pool.acquire() as conn:
                    await conn.execute("""
                        INSERT INTO pending_actions
                        (id, session_id, user_id, user_role, action_type, tool_name,
                         action_params, confirmation_message, status, created_at,
                         expires_at, langgraph_thread_id, langgraph_checkpoint_id)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                    """,
                        action_id, session_id, user_id, user_role, action_type, tool_name,
                        json.dumps(action_params), confirmation_message, ActionStatus.PENDING.value,
                        now, expires_at, langgraph_thread_id, langgraph_checkpoint_id
                    )
                logger.info(f"Created pending action in PostgreSQL: {action_id}")
            except Exception as e:
                logger.error(f"Failed to store pending action in PostgreSQL: {e}")
                # Fall back to memory
                self._memory_store[action_id] = action
        else:
            # In-memory storage
            self._memory_store[action_id] = action
            logger.info(f"Created pending action in memory: {action_id}")

        return action

    async def get_pending_action(self, action_id: str) -> Optional[PendingAction]:
        """
        Get a pending action by ID

        Args:
            action_id: Action ID

        Returns:
            PendingAction or None if not found
        """
        pool = await self._get_pool()

        if pool:
            try:
                async with pool.acquire() as conn:
                    row = await conn.fetchrow(
                        "SELECT * FROM pending_actions WHERE id = $1",
                        action_id
                    )
                    if row:
                        return self._row_to_action(row)
            except Exception as e:
                logger.error(f"Failed to get pending action from PostgreSQL: {e}")

        # In-memory fallback
        return self._memory_store.get(action_id)

    async def get_pending_actions(
        self,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        status: Optional[ActionStatus] = None
    ) -> List[PendingAction]:
        """
        Get pending actions with optional filters

        Args:
            session_id: Filter by session
            user_id: Filter by user
            status: Filter by status

        Returns:
            List of matching PendingActions
        """
        pool = await self._get_pool()

        if pool:
            try:
                async with pool.acquire() as conn:
                    query = "SELECT * FROM pending_actions WHERE 1=1"
                    params = []
                    param_count = 0

                    if session_id:
                        param_count += 1
                        query += f" AND session_id = ${param_count}"
                        params.append(session_id)

                    if user_id:
                        param_count += 1
                        query += f" AND user_id = ${param_count}"
                        params.append(user_id)

                    if status:
                        param_count += 1
                        query += f" AND status = ${param_count}"
                        params.append(status.value)

                    query += " ORDER BY created_at DESC"

                    rows = await conn.fetch(query, *params)
                    return [self._row_to_action(row) for row in rows]
            except Exception as e:
                logger.error(f"Failed to get pending actions from PostgreSQL: {e}")

        # In-memory fallback
        actions = list(self._memory_store.values())

        if session_id:
            actions = [a for a in actions if a.session_id == session_id]
        if user_id:
            actions = [a for a in actions if a.user_id == user_id]
        if status:
            actions = [a for a in actions if a.status == status]

        return sorted(actions, key=lambda a: a.created_at, reverse=True)

    async def approve_action(
        self,
        action_id: str,
        approved_by: str,
        resolution_note: Optional[str] = None
    ) -> Optional[PendingAction]:
        """
        Approve a pending action

        Args:
            action_id: Action to approve
            approved_by: User approving
            resolution_note: Optional note

        Returns:
            Updated PendingAction or None if not found/expired
        """
        action = await self.get_pending_action(action_id)

        if not action:
            logger.warning(f"Action not found: {action_id}")
            return None

        if action.is_expired():
            await self._update_status(action_id, ActionStatus.EXPIRED)
            logger.warning(f"Action expired: {action_id}")
            return None

        if action.status != ActionStatus.PENDING:
            logger.warning(f"Action already resolved: {action_id} ({action.status})")
            return action

        return await self._update_status(
            action_id,
            ActionStatus.APPROVED,
            resolution_note=resolution_note
        )

    async def reject_action(
        self,
        action_id: str,
        rejected_by: str,
        resolution_note: Optional[str] = None
    ) -> Optional[PendingAction]:
        """
        Reject a pending action

        Args:
            action_id: Action to reject
            rejected_by: User rejecting
            resolution_note: Optional reason

        Returns:
            Updated PendingAction or None if not found
        """
        return await self._update_status(
            action_id,
            ActionStatus.REJECTED,
            resolution_note=resolution_note
        )

    async def mark_executed(
        self,
        action_id: str,
        success: bool = True,
        resolution_note: Optional[str] = None
    ) -> Optional[PendingAction]:
        """
        Mark action as executed (after approval and execution)

        Args:
            action_id: Action that was executed
            success: Whether execution succeeded
            resolution_note: Execution result note

        Returns:
            Updated PendingAction
        """
        status = ActionStatus.EXECUTED if success else ActionStatus.FAILED
        return await self._update_status(action_id, status, resolution_note=resolution_note)

    async def _update_status(
        self,
        action_id: str,
        new_status: ActionStatus,
        resolution_note: Optional[str] = None
    ) -> Optional[PendingAction]:
        """Update action status in storage"""
        now = datetime.utcnow()
        pool = await self._get_pool()

        if pool:
            try:
                async with pool.acquire() as conn:
                    await conn.execute("""
                        UPDATE pending_actions
                        SET status = $1, resolved_at = $2, resolution_note = $3
                        WHERE id = $4
                    """, new_status.value, now, resolution_note, action_id)
                logger.info(f"Updated action status in PostgreSQL: {action_id} -> {new_status}")
            except Exception as e:
                logger.error(f"Failed to update action in PostgreSQL: {e}")

        # Update in-memory (always, for consistency)
        if action_id in self._memory_store:
            self._memory_store[action_id].status = new_status
            self._memory_store[action_id].resolved_at = now
            self._memory_store[action_id].resolution_note = resolution_note

        return await self.get_pending_action(action_id)

    def _row_to_action(self, row: Any) -> PendingAction:
        """Convert database row to PendingAction"""
        return PendingAction(
            id=str(row['id']),
            session_id=row['session_id'],
            user_id=row['user_id'],
            user_role=row['user_role'],
            action_type=row['action_type'],
            tool_name=row['tool_name'],
            action_params=json.loads(row['action_params']) if isinstance(row['action_params'], str) else row['action_params'],
            confirmation_message=row['confirmation_message'],
            status=ActionStatus(row['status']),
            created_at=row['created_at'],
            expires_at=row['expires_at'],
            langgraph_thread_id=row.get('langgraph_thread_id'),
            langgraph_checkpoint_id=row.get('langgraph_checkpoint_id'),
            resolved_at=row.get('resolved_at'),
            resolution_note=row.get('resolution_note')
        )

    async def cleanup_expired(self) -> int:
        """
        Mark expired pending actions as expired

        Returns:
            Number of actions marked as expired
        """
        now = datetime.utcnow()
        count = 0

        pool = await self._get_pool()

        if pool:
            try:
                async with pool.acquire() as conn:
                    result = await conn.execute("""
                        UPDATE pending_actions
                        SET status = 'expired', resolved_at = $1
                        WHERE status = 'pending' AND expires_at < $1
                    """, now)
                    count = int(result.split()[-1])
                    logger.info(f"Cleaned up {count} expired actions in PostgreSQL")
            except Exception as e:
                logger.error(f"Failed to cleanup expired actions: {e}")

        # In-memory cleanup
        for action_id, action in list(self._memory_store.items()):
            if action.status == ActionStatus.PENDING and action.is_expired():
                action.status = ActionStatus.EXPIRED
                action.resolved_at = now
                count += 1

        return count


# Global store instance (initialized without database URL - will use in-memory)
# In production, initialize with database_url from settings
pending_actions_store = PendingActionsStore()
