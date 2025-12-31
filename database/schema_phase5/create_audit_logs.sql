-- ============================================================================
-- Phase 5: Audit Logs Table (PostgreSQL)
-- Comprehensive Action and Access Audit Trail
-- ============================================================================
-- This table stores all action attempts, approvals, rejections, and executions.
-- Critical for compliance, security auditing, and troubleshooting.
-- ============================================================================

-- Drop table if exists (for clean migration)
DROP TABLE IF EXISTS audit_logs CASCADE;

-- Create audit_logs table
CREATE TABLE audit_logs (
    -- Primary identifier
    id BIGSERIAL PRIMARY KEY,

    -- Actor information
    user_id VARCHAR(50) NOT NULL,
    user_role VARCHAR(20) NOT NULL,
    session_id VARCHAR(100),

    -- Action classification
    event_type VARCHAR(50) NOT NULL,
    -- Values: action_requested, action_approved, action_rejected, action_executed,
    --         action_failed, action_expired, permission_denied, tool_executed

    action_type VARCHAR(50),           -- grant_access, block_access, revoke_access, query, report
    tool_name VARCHAR(100),            -- Tool that was used

    -- Target entity
    target_type VARCHAR(50),           -- user, door, zone, permission, query, report
    target_id VARCHAR(100),
    target_description VARCHAR(255),

    -- Request details
    request_params JSONB DEFAULT '{}',

    -- Result details
    status VARCHAR(20) NOT NULL,       -- success, failure, denied, timeout
    result_data JSONB DEFAULT '{}',
    error_message TEXT,

    -- Linked pending action (if applicable)
    pending_action_id UUID REFERENCES pending_actions(id),

    -- Context
    ip_address INET,
    user_agent TEXT,

    -- Timing
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    execution_time_ms INTEGER,         -- How long the action took

    -- Additional metadata
    metadata JSONB DEFAULT '{}'
);

-- ============================================================================
-- Indexes for common queries
-- ============================================================================

-- Find logs by user
CREATE INDEX idx_audit_logs_user
ON audit_logs(user_id, timestamp DESC);

-- Find logs by session
CREATE INDEX idx_audit_logs_session
ON audit_logs(session_id, timestamp DESC);

-- Find logs by event type
CREATE INDEX idx_audit_logs_event
ON audit_logs(event_type, timestamp DESC);

-- Find logs by action type
CREATE INDEX idx_audit_logs_action
ON audit_logs(action_type, timestamp DESC);

-- Find logs by target
CREATE INDEX idx_audit_logs_target
ON audit_logs(target_type, target_id, timestamp DESC);

-- Date range queries (partitioning-friendly)
CREATE INDEX idx_audit_logs_timestamp
ON audit_logs(timestamp DESC);

-- Find failed actions
CREATE INDEX idx_audit_logs_status
ON audit_logs(status)
WHERE status != 'success';

-- ============================================================================
-- Comments for documentation
-- ============================================================================

COMMENT ON TABLE audit_logs IS
'Comprehensive audit trail for all chatbot actions and access attempts';

COMMENT ON COLUMN audit_logs.event_type IS
'Type of event: action_requested, action_approved, action_rejected, action_executed, action_failed, action_expired, permission_denied, tool_executed';

COMMENT ON COLUMN audit_logs.status IS
'Outcome: success, failure, denied, timeout';

-- ============================================================================
-- Helper view for recent activity
-- ============================================================================

CREATE OR REPLACE VIEW recent_audit_activity AS
SELECT
    al.id,
    al.timestamp,
    al.user_id,
    al.user_role,
    al.event_type,
    al.action_type,
    al.target_description,
    al.status,
    al.execution_time_ms,
    al.error_message
FROM audit_logs al
WHERE al.timestamp > CURRENT_TIMESTAMP - INTERVAL '24 hours'
ORDER BY al.timestamp DESC;

COMMENT ON VIEW recent_audit_activity IS
'Quick view of audit events from the last 24 hours';

-- ============================================================================
-- Helper view for action summary
-- ============================================================================

CREATE OR REPLACE VIEW action_summary AS
SELECT
    action_type,
    status,
    COUNT(*) as count,
    AVG(execution_time_ms) as avg_execution_time_ms,
    DATE_TRUNC('day', timestamp) as date
FROM audit_logs
WHERE action_type IS NOT NULL
GROUP BY action_type, status, DATE_TRUNC('day', timestamp)
ORDER BY date DESC, action_type;

COMMENT ON VIEW action_summary IS
'Daily summary of actions by type and status';

-- ============================================================================
-- Function to log audit events (can be called from application)
-- ============================================================================

CREATE OR REPLACE FUNCTION log_audit_event(
    p_user_id VARCHAR(50),
    p_user_role VARCHAR(20),
    p_session_id VARCHAR(100),
    p_event_type VARCHAR(50),
    p_action_type VARCHAR(50),
    p_tool_name VARCHAR(100),
    p_target_type VARCHAR(50),
    p_target_id VARCHAR(100),
    p_target_description VARCHAR(255),
    p_status VARCHAR(20),
    p_request_params JSONB DEFAULT '{}',
    p_result_data JSONB DEFAULT '{}',
    p_error_message TEXT DEFAULT NULL,
    p_execution_time_ms INTEGER DEFAULT NULL,
    p_pending_action_id UUID DEFAULT NULL,
    p_metadata JSONB DEFAULT '{}'
)
RETURNS BIGINT AS $$
DECLARE
    new_id BIGINT;
BEGIN
    INSERT INTO audit_logs (
        user_id, user_role, session_id, event_type, action_type, tool_name,
        target_type, target_id, target_description, status,
        request_params, result_data, error_message, execution_time_ms,
        pending_action_id, metadata
    ) VALUES (
        p_user_id, p_user_role, p_session_id, p_event_type, p_action_type, p_tool_name,
        p_target_type, p_target_id, p_target_description, p_status,
        p_request_params, p_result_data, p_error_message, p_execution_time_ms,
        p_pending_action_id, p_metadata
    )
    RETURNING id INTO new_id;

    RETURN new_id;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION log_audit_event IS
'Helper function to insert audit log entries with all required fields';

-- ============================================================================
-- Cleanup function for old logs (retention policy)
-- ============================================================================

CREATE OR REPLACE FUNCTION cleanup_old_audit_logs(retention_days INTEGER DEFAULT 90)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM audit_logs
    WHERE timestamp < CURRENT_TIMESTAMP - (retention_days || ' days')::INTERVAL;

    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION cleanup_old_audit_logs IS
'Delete audit logs older than specified days. Default: 90 days retention.';

SELECT 'audit_logs table created successfully' AS result;
