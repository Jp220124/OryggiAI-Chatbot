"""
Platform Base Model
Provides common functionality for all platform models
"""

import uuid
from datetime import datetime
from typing import Any, Dict

from sqlalchemy import Column, DateTime, event
from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER
from sqlalchemy.ext.declarative import declarative_base, declared_attr
from sqlalchemy.orm import Session


class PlatformBaseClass:
    """
    Base class for all platform models.
    Provides common columns and methods.
    """

    # Allow legacy type annotations without Mapped[] wrapper
    __allow_unmapped__ = True

    @declared_attr
    def __tablename__(cls) -> str:
        """Auto-generate table name from class name (snake_case)"""
        # Convert CamelCase to snake_case
        name = cls.__name__
        return ''.join(
            ['_' + c.lower() if c.isupper() else c for c in name]
        ).lstrip('_')

    # Common columns
    id = Column(
        UNIQUEIDENTIFIER,
        primary_key=True,
        default=uuid.uuid4,
        nullable=False
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    def to_dict(self, exclude: list = None) -> Dict[str, Any]:
        """
        Convert model instance to dictionary.

        Args:
            exclude: List of column names to exclude

        Returns:
            Dictionary representation of the model
        """
        exclude = exclude or []
        result = {}

        for column in self.__table__.columns:
            if column.name not in exclude:
                value = getattr(self, column.name)

                # Handle special types
                if isinstance(value, datetime):
                    value = value.isoformat()
                elif isinstance(value, uuid.UUID):
                    value = str(value)

                result[column.name] = value

        return result

    def update_from_dict(self, data: Dict[str, Any], exclude: list = None) -> None:
        """
        Update model from dictionary.

        Args:
            data: Dictionary with new values
            exclude: List of column names to exclude from update
        """
        exclude = exclude or ['id', 'created_at']

        for key, value in data.items():
            if key not in exclude and hasattr(self, key):
                setattr(self, key, value)

    @classmethod
    def get_by_id(cls, session: Session, id: uuid.UUID):
        """
        Get model instance by ID.

        Args:
            session: SQLAlchemy session
            id: Record UUID

        Returns:
            Model instance or None
        """
        return session.query(cls).filter(cls.id == id).first()

    def __repr__(self) -> str:
        """String representation of model"""
        return f"<{self.__class__.__name__}(id={self.id})>"


# Create the declarative base
PlatformBase = declarative_base(cls=PlatformBaseClass)


# Event listener to auto-update updated_at
@event.listens_for(PlatformBase, 'before_update', propagate=True)
def receive_before_update(mapper, connection, target):
    """Auto-update the updated_at timestamp before any update"""
    target.updated_at = datetime.utcnow()
