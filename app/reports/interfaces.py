"""
Report Generator Interfaces
Defines abstract contracts for all report generators (PDF, Excel, etc.)

This enables:
- Pluggable report generators (swap implementations without code changes)
- Dependency Injection (pass generators to tools instead of hardcoding)
- SOLID Principles compliance (Dependency Inversion, Open/Closed)
- True Microservices Architecture (loose coupling, independent deployment)
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional


class ReportGenerator(ABC):
    """
    Abstract base class for all report generators

    Contract:
    - All generators must implement async generate_table_report()
    - All generators must return file path to generated report
    - All generators must accept same parameters for consistency

    Benefits:
    - Any generator can be swapped without changing caller code
    - New generators can be added without modifying existing code
    - Tools depend on interface, not concrete implementations (DIP)
    """

    @abstractmethod
    async def generate_table_report(
        self,
        query_results: List[Dict[str, Any]],
        title: str,
        user_id: str,
        user_role: str,
        question: str,
        sql_query: str,
        filename: Optional[str] = None,
        max_rows: Optional[int] = None
    ) -> str:
        """
        Generate report from database query results

        Args:
            query_results: List of query result dictionaries
            title: Report title
            user_id: User identifier who requested the report
            user_role: User's role (for audit logging)
            question: Original natural language question
            sql_query: SQL query that was executed
            filename: Optional custom filename (auto-generated if None)
            max_rows: Maximum rows to include in report

        Returns:
            str: Absolute path to generated report file

        Raises:
            RuntimeError: If report generation fails
        """
        pass

    @property
    @abstractmethod
    def format_name(self) -> str:
        """
        Return the format name (e.g., 'pdf', 'excel', 'csv')

        Used for:
        - Factory registration
        - User-facing format selection
        - Logging and audit trails
        """
        pass

    @property
    @abstractmethod
    def file_extension(self) -> str:
        """
        Return the file extension (e.g., '.pdf', '.xlsx', '.csv')

        Used for:
        - Auto-generating filenames
        - Setting HTTP Content-Type headers
        - File type validation
        """
        pass

    @property
    @abstractmethod
    def mime_type(self) -> str:
        """
        Return the MIME type (e.g., 'application/pdf', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

        Used for:
        - HTTP Content-Type headers
        - Email attachments
        - Browser download handling
        """
        pass
