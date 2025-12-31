-- ============================================================================
-- Phase 5: Pending Actions Table (PostgreSQL)
-- Human-in-the-Loop Action Confirmation Storage
-- ============================================================================
-- This table stores actions that require user confirmation before execution.
-- Used with LangGraph's interrupt() pattern for destructive operations.
-- ============================================================================

-- Drop table if exists (for clean migration)
DROP TABLE IF EXISTS pending_actions CASCADE;

-- Create pending_actions table
CREATE TABLE pending_actions (
    -- Primary identifier (UUID for security - no guessable IDs)
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Session and user context
    session_id VARCHAR(100) NOT NULL,
    user_id VARCHAR(50) NOT NULL,
    user_role VARCHAR(20) NOT NULL,

    -- Action details
    action_type VARCHAR(50) NOT NULL,  -- grant_access, block_access, revoke_access, modify_permission
    tool_name VARCHAR(100) NOT NULL,   -- The tool that will execute this action

    -- Action parameters (flexible JSON structure)
    action_params JSONB NOT NULL DEFAULT '{}',

    -- Human-readable confirmation message shown to user
    confirmation_message TEXT NOT NULL,

    -- Target entity information (for audit)
    target_type VARCHAR(50),           -- user, door, zone, permission
    target_id VARCHAR(100),            -- ID of the target entity
    target_description VARCHAR(255),   -- Human-readable description

    -- Status tracking
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    -- Values: pending, approved, rejected, expired, executed, failed

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    resolved_at TIMESTAMP WITH TIME ZONE,
    executed_at TIMESTAMP WITH TIME ZONE,

    -- Resolution details
    resolved_by VARCHAR(50),           -- User who approved/rejected
    resolution_note TEXT,              -- Optional note on approval/rejection

    -- Execution result (if executed)
    execution_result JSONB,
    execution_error TEXT,

    -- LangGraph state reference (for resuming workflow)
    langgraph_thread_id VARCHAR(100),
    langgraph_checkpoint_id VARCHAR(100),

    -- Metadata
    metadata JSONB DEFAULT '{}'
);

-- ============================================================================
-- Indexes for common queries
-- ============================================================================

-- Find pending actions for a user
CREATE INDEX idx_pending_actions_user_status
ON pending_actions(user_id, status);

-- Find pending actions for a session
CREATE INDEX idx_pending_actions_session
ON pending_actions(session_id, status);

-- Find expired actions (for cleanup job)
CREATE INDEX idx_pending_actions_expires
ON pending_actions(expires_at)
WHERE status = 'pending';

-- Find actions by type for analytics
CREATE INDEX idx_pending_actions_type
ON pending_actions(action_type, created_at);

-- LangGraph thread lookup
CREATE INDEX idx_pending_actions_langgraph
ON pending_actions(langgraph_thread_id);

-- ============================================================================
-- Comments for documentation
-- ============================================================================

COMMENT ON TABLE pending_actions IS
'Stores actions requiring user confirmation before execution (Human-in-the-Loop pattern)';

COMMENT ON COLUMN pending_actions.status IS
'pending: awaiting response, approved: user confirmed, rejected: user declined, expired: timeout, executed: completed, failed: execution error';

COMMENT ON COLUMN pending_actions.expires_at IS
'Action must be confirmed before this time (default: 5 minutes from creation)';

-- ============================================================================
-- Function to auto-expire pending actions
-- ============================================================================

CREATE OR REPLACE FUNCTION expire_pending_actions()
RETURNS INTEGER AS $$
DECLARE
    expired_count INTEGER;
BEGIN
    UPDATE pending_actions
    SET status = 'expired',
        resolved_at = CURRENT_TIMESTAMP,
        resolution_note = 'Auto-expired due to timeout'
    WHERE status = 'pending'
      AND expires_at < CURRENT_TIMESTAMP;

    GET DIAGNOSTICS expired_count = ROW_COUNT;
    RETURN expired_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION expire_pending_actions() IS
'Marks pending actions as expired if they exceed their timeout. Call periodically via cron or application.';

-- ============================================================================
-- Sample data for testing
-- ============================================================================

-- INSERT INTO pending_actions (
--     session_id, user_id, user_role, action_type, tool_name,
--     action_params, confirmation_message, target_type, target_id,
--     target_description, expires_at
-- ) VALUES (
--     'session_admin_test', 'admin', 'ADMIN', 'grant_access', 'grant_access_tool',
--     '{"user_id": 123, "door_id": 45, "start_date": "2025-01-22", "end_date": "2025-12-31"}',
--     'Grant access for John Doe (ID: 123) to Server Room (Door: 45) from 2025-01-22 to 2025-12-31?',
--     'user', '123', 'John Doe - IT Department',
--     CURRENT_TIMESTAMP + INTERVAL '5 minutes'
-- );

SELECT 'pending_actions table created successfully' AS result;
