"""
On-Premises Data Gateway Module

Enables clients to connect their on-premises databases to the SaaS platform
through outbound WebSocket connections, bypassing firewall restrictions.

Architecture:
    Client Network                    SaaS Server
    ┌───────────┐                    ┌───────────┐
    │  Gateway  │───OUTBOUND WSS────>│ WebSocket │
    │   Agent   │<───────────────────│ Endpoint  │
    └─────┬─────┘                    └─────┬─────┘
          │                                │
          v                                v
    ┌───────────┐                   TenantSQLAgent
    │ SQL Server│                    (LLM + RAG)
    └───────────┘

Components:
    - GatewayConnectionManager: Manages WebSocket connections from agents
    - MessageHandler: Processes agent messages (auth, query, heartbeat)
    - QueryRouter: Routes queries to gateway or direct connection
    - Schemas: Pydantic models for message protocol
"""

from app.gateway.connection_manager import GatewayConnectionManager, gateway_manager
from app.gateway.query_router import QueryRouter, query_router
from app.gateway.exceptions import (
    GatewayException,
    GatewayAuthenticationError,
    GatewayConnectionError,
    GatewayTimeoutError,
    GatewayQueryError,
)

__all__ = [
    "GatewayConnectionManager",
    "gateway_manager",
    "QueryRouter",
    "query_router",
    "GatewayException",
    "GatewayAuthenticationError",
    "GatewayConnectionError",
    "GatewayTimeoutError",
    "GatewayQueryError",
]
