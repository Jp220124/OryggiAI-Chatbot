"""
API Module
FastAPI routers for all endpoints
"""

from app.api.chat import router as chat_router
from app.api.actions import router as actions_router
from app.api.auth import router as auth_router
from app.api.tenant import router as tenant_router

__all__ = ["chat_router", "actions_router", "auth_router", "tenant_router"]
