"""
Report Formatter
Utilities for formatting query results into report-ready structures
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import pandas as pd
from loguru import logger


class ReportFormatter:
    """
    Format query results for PDF/Excel reports
    """

    @staticmethod
    def format_query_results(
        query_results: List[Dict[str, Any]],
        title: str,
        max_rows: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Format query results into report structure

        Args:
            query_results: List of dicts from database query
            title: Report title
            max_rows: Maximum rows to include (None for unlimited)

        Returns:
            Formatted report data structure
        """
        if not query_results:
            return {
                "title": title,
                "columns": [],
                "rows": [],
                "total_rows": 0,
                "generated_at": datetime.now().isoformat(),
                "truncated": False
            }

        # Extract columns from first row
        columns = list(query_results[0].keys())

        # Apply row limit if specified
        total_rows = len(query_results)
        truncated = False

        if max_rows and total_rows > max_rows:
            query_results = query_results[:max_rows]
            truncated = True
            logger.warning(f"Report truncated: {total_rows} rows -> {max_rows} rows")

        # Format rows
        rows = []
        for result in query_results:
            row = []
            for col in columns:
                value = result.get(col)
                formatted_value = ReportFormatter._format_cell_value(value)
                row.append(formatted_value)
            rows.append(row)

        return {
            "title": title,
            "columns": columns,
            "rows": rows,
            "total_rows": total_rows,
            "displayed_rows": len(rows),
            "generated_at": datetime.now().isoformat(),
            "truncated": truncated
        }

    @staticmethod
    def _format_cell_value(value: Any) -> str:
        """
        Format individual cell value for display

        Args:
            value: Cell value

        Returns:
            Formatted string value
        """
        if value is None:
            return "N/A"
        elif isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M:%S")
        elif isinstance(value, (int, float)):
            return str(value)
        elif isinstance(value, bool):
            return "Yes" if value else "No"
        else:
            return str(value)

    @staticmethod
    def to_dataframe(formatted_data: Dict[str, Any]) -> pd.DataFrame:
        """
        Convert formatted data to pandas DataFrame

        Args:
            formatted_data: Output from format_query_results()

        Returns:
            pandas DataFrame
        """
        if not formatted_data["rows"]:
            return pd.DataFrame()

        df = pd.DataFrame(
            formatted_data["rows"],
            columns=formatted_data["columns"]
        )

        return df

    @staticmethod
    def create_summary_stats(df: pd.DataFrame) -> Dict[str, Any]:
        """
        Generate summary statistics from DataFrame

        Args:
            df: pandas DataFrame

        Returns:
            Dictionary of summary statistics
        """
        if df.empty:
            return {
                "total_rows": 0,
                "total_columns": 0,
                "numeric_columns": [],
                "date_columns": [],
                "text_columns": []
            }

        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        date_cols = df.select_dtypes(include=['datetime64']).columns.tolist()
        text_cols = df.select_dtypes(include=['object']).columns.tolist()

        stats = {
            "total_rows": len(df),
            "total_columns": len(df.columns),
            "numeric_columns": numeric_cols,
            "date_columns": date_cols,
            "text_columns": text_cols
        }

        # Add numeric summaries
        if numeric_cols:
            stats["numeric_summary"] = {}
            for col in numeric_cols:
                stats["numeric_summary"][col] = {
                    "min": float(df[col].min()),
                    "max": float(df[col].max()),
                    "mean": float(df[col].mean()),
                    "median": float(df[col].median()),
                    "sum": float(df[col].sum())
                }

        return stats

    @staticmethod
    def add_metadata(
        formatted_data: Dict[str, Any],
        user_id: str,
        user_role: str,
        question: str,
        sql_query: str
    ) -> Dict[str, Any]:
        """
        Add metadata to formatted report data

        Args:
            formatted_data: Formatted report data
            user_id: User who generated report
            user_role: User's role
            question: Original question
            sql_query: SQL query executed

        Returns:
            Enhanced data with metadata
        """
        formatted_data["metadata"] = {
            "generated_by": user_id,
            "user_role": user_role,
            "question": question,
            "sql_query": sql_query,
            "generated_at": datetime.now().isoformat()
        }

        return formatted_data
