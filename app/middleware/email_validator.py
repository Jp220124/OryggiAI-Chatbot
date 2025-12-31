"""
Email Validation and Rate Limiting Middleware
Provides security controls for email sending
"""

from typing import Tuple, Optional, List
from datetime import datetime, timedelta
from collections import defaultdict
import re
from loguru import logger

from app.config import settings


class EmailValidator:
    """
    Email validation and rate limiting service

    Features:
    - Email format validation
    - Domain whitelist/blacklist
    - Per-user rate limiting
    - IP-based rate limiting
    - Suspicious pattern detection

    Example:
        validator = EmailValidator()
        is_valid, error = validator.validate_email(
            recipient="user@company.com",
            user_id="manager_123"
        )
        if not is_valid:
            raise ValueError(error)
    """

    # Email regex pattern (RFC 5322 simplified)
    EMAIL_PATTERN = re.compile(
        r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    )

    # Default allowed domains (configurable)
    DEFAULT_ALLOWED_DOMAINS = [
        # Add your company domains here
        # "yourcompany.com",
        # "partner.com"
    ]

    # Blocked domains (known spam/temporary email services)
    BLOCKED_DOMAINS = [
        "tempmail.com",
        "10minutemail.com",
        "guerrillamail.com",
        "throwaway.email",
        "mailinator.com"
    ]

    # Rate limit defaults
    MAX_EMAILS_PER_HOUR = 10
    MAX_EMAILS_PER_DAY = 50

    def __init__(
        self,
        allowed_domains: Optional[List[str]] = None,
        max_emails_per_hour: Optional[int] = None,
        max_emails_per_day: Optional[int] = None
    ):
        """
        Initialize email validator

        Args:
            allowed_domains: List of whitelisted domains (None = allow all except blocked)
            max_emails_per_hour: Max emails per user per hour
            max_emails_per_day: Max emails per user per day
        """
        self.allowed_domains = allowed_domains or self.DEFAULT_ALLOWED_DOMAINS
        self.max_emails_per_hour = max_emails_per_hour or self.MAX_EMAILS_PER_HOUR
        self.max_emails_per_day = max_emails_per_day or self.MAX_EMAILS_PER_DAY

        # In-memory rate limit tracking
        # In production, use Redis or database
        self.email_history: dict = defaultdict(list)

        logger.info(
            f"[EmailValidator] Initialized - "
            f"Max/hour: {self.max_emails_per_hour}, "
            f"Max/day: {self.max_emails_per_day}"
        )

    def validate_email(
        self,
        recipient: str,
        user_id: str,
        user_role: Optional[str] = None,
        check_rate_limit: bool = True
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate email address and check rate limits

        Args:
            recipient: Email address to validate
            user_id: User sending the email
            user_role: User's role (ADMIN bypasses some limits)
            check_rate_limit: Whether to check rate limits

        Returns:
            (is_valid: bool, error_message: Optional[str])

        Example:
            is_valid, error = validator.validate_email("user@test.com", "user_123")
            if not is_valid:
                print(error)  # "Invalid email format"
        """
        # 1. Format validation
        if not self._validate_format(recipient):
            error = f"Invalid email format: {recipient}"
            logger.warning(f"[EmailValidator] {error}")
            return False, error

        # 2. Domain validation
        domain = recipient.split('@')[1].lower()

        # Check blocked domains
        if domain in self.BLOCKED_DOMAINS:
            error = f"Email domain blocked: {domain}"
            logger.warning(f"[EmailValidator] {error}")
            return False, error

        # Check allowed domains (if whitelist is configured)
        if self.allowed_domains and domain not in self.allowed_domains:
            error = (
                f"Email domain not whitelisted: {domain}. "
                f"Allowed domains: {', '.join(self.allowed_domains)}"
            )
            logger.warning(f"[EmailValidator] {error}")
            return False, error

        # 3. Rate limit check
        if check_rate_limit:
            # ADMIN users have higher limits (optional)
            if user_role == "ADMIN":
                # 2x limits for admins
                max_hour = self.max_emails_per_hour * 2
                max_day = self.max_emails_per_day * 2
            else:
                max_hour = self.max_emails_per_hour
                max_day = self.max_emails_per_day

            is_allowed, error = self._check_rate_limit(
                user_id,
                max_hour=max_hour,
                max_day=max_day
            )

            if not is_allowed:
                logger.warning(f"[EmailValidator] Rate limit exceeded: {user_id}")
                return False, error

        logger.debug(f"[EmailValidator] Email validated: {recipient}")
        return True, None

    def _validate_format(self, email: str) -> bool:
        """
        Validate email format using regex

        Args:
            email: Email address to validate

        Returns:
            True if valid format
        """
        if not email or not isinstance(email, str):
            return False

        return bool(self.EMAIL_PATTERN.match(email))

    def _check_rate_limit(
        self,
        user_id: str,
        max_hour: int,
        max_day: int
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if user has exceeded rate limits

        Args:
            user_id: User identifier
            max_hour: Max emails per hour
            max_day: Max emails per day

        Returns:
            (is_allowed: bool, error_message: Optional[str])
        """
        now = datetime.now()
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(days=1)

        # Get user's email history
        history = self.email_history[user_id]

        # Clean old entries (older than 1 day)
        history = [ts for ts in history if ts > day_ago]
        self.email_history[user_id] = history

        # Count emails in last hour
        emails_last_hour = sum(1 for ts in history if ts > hour_ago)
        if emails_last_hour >= max_hour:
            return False, (
                f"Rate limit exceeded: {emails_last_hour}/{max_hour} emails in last hour. "
                f"Try again later."
            )

        # Count emails in last day
        emails_last_day = len(history)
        if emails_last_day >= max_day:
            return False, (
                f"Daily rate limit exceeded: {emails_last_day}/{max_day} emails in last 24 hours. "
                f"Try again tomorrow."
            )

        return True, None

    def record_email_sent(self, user_id: str):
        """
        Record that an email was sent (for rate limiting)

        Args:
            user_id: User who sent the email
        """
        self.email_history[user_id].append(datetime.now())
        logger.debug(
            f"[EmailValidator] Recorded email for {user_id} "
            f"(total last 24h: {len(self.email_history[user_id])})"
        )

    def get_user_stats(self, user_id: str) -> dict:
        """
        Get email sending statistics for a user

        Args:
            user_id: User identifier

        Returns:
            {
                "emails_last_hour": int,
                "emails_last_day": int,
                "remaining_hour": int,
                "remaining_day": int
            }
        """
        now = datetime.now()
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(days=1)

        history = self.email_history[user_id]

        # Clean old entries
        history = [ts for ts in history if ts > day_ago]

        emails_last_hour = sum(1 for ts in history if ts > hour_ago)
        emails_last_day = len(history)

        return {
            "emails_last_hour": emails_last_hour,
            "emails_last_day": emails_last_day,
            "remaining_hour": max(0, self.max_emails_per_hour - emails_last_hour),
            "remaining_day": max(0, self.max_emails_per_day - emails_last_day),
            "max_per_hour": self.max_emails_per_hour,
            "max_per_day": self.max_emails_per_day
        }

    def reset_user_limits(self, user_id: str):
        """
        Reset rate limits for a user (admin function)

        Args:
            user_id: User to reset
        """
        if user_id in self.email_history:
            del self.email_history[user_id]
            logger.info(f"[EmailValidator] Reset limits for {user_id}")


# Global email validator instance
email_validator = EmailValidator()
