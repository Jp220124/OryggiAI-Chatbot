-- Database Initialization Script for Chatbot Conversation History
-- This script creates the ConversationHistory table with all required fields
-- Automatically executed when PostgreSQL container starts for the first time

-- Create ConversationHistory table
CREATE TABLE IF NOT EXISTS ConversationHistory (
    -- Primary key
    conversation_id SERIAL PRIMARY KEY,

    -- Session and user identification
    session_id VARCHAR(255) NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    user_role VARCHAR(50) NOT NULL,

    -- Message content
    message_type VARCHAR(20) NOT NULL CHECK (message_type IN ('user', 'assistant', 'system')),
    message_content TEXT NOT NULL,

    -- Metadata
    tools_used TEXT[],  -- Array of tool names used
    success_flag BOOLEAN DEFAULT TRUE,
    error_message TEXT,

    -- Timestamps
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Soft delete
    is_active BOOLEAN DEFAULT TRUE,

    -- Indexes for common queries
    CONSTRAINT unique_session_timestamp UNIQUE (session_id, timestamp)
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_session_id ON ConversationHistory(session_id);
CREATE INDEX IF NOT EXISTS idx_user_id ON ConversationHistory(user_id);
CREATE INDEX IF NOT EXISTS idx_timestamp ON ConversationHistory(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_session_user ON ConversationHistory(session_id, user_id);
CREATE INDEX IF NOT EXISTS idx_active_messages ON ConversationHistory(is_active) WHERE is_active = TRUE;

-- Create a function to get conversation statistics
CREATE OR REPLACE FUNCTION get_conversation_stats(p_user_id VARCHAR)
RETURNS TABLE (
    total_sessions BIGINT,
    total_messages BIGINT,
    total_user_messages BIGINT,
    total_assistant_messages BIGINT,
    latest_message_time TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        COUNT(DISTINCT session_id)::BIGINT as total_sessions,
        COUNT(*)::BIGINT as total_messages,
        COUNT(*) FILTER (WHERE message_type = 'user')::BIGINT as total_user_messages,
        COUNT(*) FILTER (WHERE message_type = 'assistant')::BIGINT as total_assistant_messages,
        MAX(timestamp) as latest_message_time
    FROM ConversationHistory
    WHERE user_id = p_user_id AND is_active = TRUE;
END;
$$ LANGUAGE plpgsql;

-- Insert welcome message to verify database is working
INSERT INTO ConversationHistory (
    session_id,
    user_id,
    user_role,
    message_type,
    message_content,
    success_flag
) VALUES (
    'system_init_' || NOW()::TEXT,
    'system',
    'ADMIN',
    'system',
    'PostgreSQL database initialized successfully for Advance Chatbot - Phase 3 Memory System',
    TRUE
);

-- Output confirmation
DO $$
BEGIN
    RAISE NOTICE 'ConversationHistory table created successfully';
    RAISE NOTICE 'Indexes created for optimal query performance';
    RAISE NOTICE 'Helper functions created';
    RAISE NOTICE 'Database is ready for use!';
END $$;
