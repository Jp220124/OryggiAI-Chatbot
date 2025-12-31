"""
Smart Chart Selector Module
Automatically determines the best chart type based on data characteristics
"""

from typing import List, Dict, Any, Optional, Tuple
import pandas as pd
from datetime import datetime


class SmartChartSelector:
    """Intelligently selects appropriate chart types based on data analysis"""

    @staticmethod
    def analyze_data(
        df: pd.DataFrame,
        column: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze data characteristics

        Args:
            df: DataFrame to analyze
            column: Specific column to analyze (None = analyze whole DataFrame)

        Returns:
            Dictionary with data characteristics
        """
        if column:
            # Analyze specific column
            col_data = df[column]
            is_numeric = pd.api.types.is_numeric_dtype(col_data)
            is_datetime = pd.api.types.is_datetime64_any_dtype(col_data)

            analysis = {
                'column_name': column,
                'num_rows': len(df),
                'num_unique': col_data.nunique(),
                'is_numeric': is_numeric,
                'is_datetime': is_datetime,
                'is_categorical': not is_numeric and not is_datetime,
                'has_nulls': col_data.isnull().any(),
                'null_percentage': (col_data.isnull().sum() / len(col_data)) * 100 if len(col_data) > 0 else 0
            }

            if is_numeric:
                analysis.update({
                    'min': float(col_data.min()),
                    'max': float(col_data.max()),
                    'mean': float(col_data.mean()),
                    'median': float(col_data.median()),
                    'std': float(col_data.std()),
                    'sum': float(col_data.sum()),
                    'is_percentage': col_data.max() <= 1.0 or (col_data.max() <= 100 and col_data.sum() == 100)
                })

        else:
            # Analyze overall DataFrame
            numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
            categorical_cols = df.select_dtypes(exclude=['number', 'datetime']).columns.tolist()
            datetime_cols = df.select_dtypes(include=['datetime']).columns.tolist()

            # Check if index is datetime
            index_is_datetime = isinstance(df.index, pd.DatetimeIndex)

            analysis = {
                'num_rows': len(df),
                'num_columns': len(df.columns),
                'numeric_columns': numeric_cols,
                'categorical_columns': categorical_cols,
                'datetime_columns': datetime_cols,
                'num_numeric': len(numeric_cols),
                'num_categorical': len(categorical_cols),
                'num_datetime': len(datetime_cols),
                'index_is_datetime': index_is_datetime,
                'has_time_series': index_is_datetime or len(datetime_cols) > 0
            }

        return analysis

    @staticmethod
    def select_chart_type(analysis: Dict[str, Any]) -> str:
        """
        Select best chart type based on data analysis

        Args:
            analysis: Data analysis dictionary from analyze_data()

        Returns:
            Recommended chart type: 'donut', 'pie', 'bar', 'horizontal_bar', 'line', 'area'
        """
        # Time series data -> Line or Area chart
        if analysis.get('has_time_series') or analysis.get('is_datetime'):
            return 'line'

        # Percentage/distribution with few categories -> Donut chart (modern pie)
        if analysis.get('is_percentage') and analysis.get('num_unique', 0) <= 6:
            return 'donut'

        # Categorical data with few categories -> Donut or Bar
        if analysis.get('is_categorical'):
            num_unique = analysis.get('num_unique', 0)
            if num_unique <= 5:
                return 'donut'  # Few categories work well in donut
            elif num_unique <= 10:
                return 'bar'
            else:
                return 'horizontal_bar'  # Better for many categories

        # Numeric data with many categories -> Bar chart
        if analysis.get('is_numeric'):
            num_unique = analysis.get('num_unique', 0)
            if num_unique <= 10:
                return 'bar'
            else:
                return 'horizontal_bar'

        # Default fallback
        return 'bar'

    @staticmethod
    def recommend_charts_for_dataset(df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Recommend appropriate charts for an entire dataset

        Args:
            df: DataFrame to analyze

        Returns:
            List of chart recommendations with specifications
        """
        recommendations = []
        analysis = SmartChartSelector.analyze_data(df)

        # Check for categorical columns that would make good donut/pie charts
        for col in analysis['categorical_columns']:
            col_analysis = SmartChartSelector.analyze_data(df, col)
            if col_analysis['num_unique'] <= 8:  # Not too many categories
                value_counts = df[col].value_counts()
                recommendations.append({
                    'type': 'donut',
                    'column': col,
                    'title': f'Distribution by {col}',
                    'data': value_counts.values.tolist(),
                    'labels': value_counts.index.tolist(),
                    'priority': 'high' if col_analysis['num_unique'] <= 5 else 'medium'
                })

        # Check for numeric columns that would make good bar charts
        for col in analysis['numeric_columns']:
            # Skip if the column has too many unique values
            if df[col].nunique() > 20:
                continue

            # Group by another categorical column if available
            if analysis['categorical_columns']:
                cat_col = analysis['categorical_columns'][0]
                grouped = df.groupby(cat_col)[col].sum().sort_values(ascending=False).head(10)

                recommendations.append({
                    'type': 'bar',
                    'column': col,
                    'grouped_by': cat_col,
                    'title': f'{col} by {cat_col}',
                    'data': grouped.values.tolist(),
                    'labels': grouped.index.tolist(),
                    'priority': 'medium'
                })

        # Check for time series data
        if analysis['has_time_series']:
            datetime_col = None
            if analysis['index_is_datetime']:
                datetime_col = 'index'
            elif analysis['datetime_columns']:
                datetime_col = analysis['datetime_columns'][0]

            if datetime_col and analysis['numeric_columns']:
                numeric_col = analysis['numeric_columns'][0]

                if datetime_col == 'index':
                    x_data = df.index.tolist()
                    y_data = df[numeric_col].tolist()
                else:
                    sorted_df = df.sort_values(datetime_col)
                    x_data = sorted_df[datetime_col].tolist()
                    y_data = sorted_df[numeric_col].tolist()

                recommendations.append({
                    'type': 'line',
                    'column': numeric_col,
                    'x_column': datetime_col,
                    'title': f'{numeric_col} Over Time',
                    'x_data': x_data,
                    'y_data': y_data,
                    'priority': 'high'
                })

        # Sort by priority
        priority_order = {'high': 0, 'medium': 1, 'low': 2}
        recommendations.sort(key=lambda x: priority_order.get(x.get('priority', 'low'), 2))

        return recommendations

    @staticmethod
    def generate_summary_stats(df: pd.DataFrame) -> Dict[str, Any]:
        """
        Generate summary statistics for KPI cards

        Args:
            df: DataFrame to analyze

        Returns:
            Dictionary with summary statistics
        """
        stats = {
            'total_rows': len(df),
            'total_columns': len(df.columns),
            'numeric_columns': [],
            'kpis': []
        }

        # Analyze numeric columns
        numeric_cols = df.select_dtypes(include=['number']).columns
        for col in numeric_cols:
            col_stats = {
                'name': col,
                'sum': float(df[col].sum()),
                'mean': float(df[col].mean()),
                'min': float(df[col].min()),
                'max': float(df[col].max()),
                'median': float(df[col].median()),
                'std': float(df[col].std())
            }
            stats['numeric_columns'].append(col_stats)

            # Create KPI for this column
            stats['kpis'].append({
                'label': f'Total {col}',
                'value': col_stats['sum'],
                'format': 'number'
            })

            stats['kpis'].append({
                'label': f'Average {col}',
                'value': col_stats['mean'],
                'format': 'decimal'
            })

        # Add row count as a KPI
        stats['kpis'].insert(0, {
            'label': 'Total Records',
            'value': stats['total_rows'],
            'format': 'number'
        })

        # Limit to top 4 KPIs for display
        stats['top_kpis'] = stats['kpis'][:4]

        return stats

    @staticmethod
    def prepare_chart_data(
        df: pd.DataFrame,
        chart_type: str,
        column: Optional[str] = None,
        limit: int = 10
    ) -> Tuple[List, List, str]:
        """
        Prepare data for a specific chart type

        Args:
            df: DataFrame
            chart_type: Type of chart ('donut', 'bar', 'line', etc.)
            column: Column to use (None = auto-select)
            limit: Maximum number of data points

        Returns:
            Tuple of (data_values, labels, title)
        """
        if column is None:
            # Auto-select column based on chart type
            if chart_type in ['donut', 'pie']:
                # Use first categorical column
                categorical_cols = df.select_dtypes(exclude=['number', 'datetime']).columns
                column = categorical_cols[0] if len(categorical_cols) > 0 else df.columns[0]
            else:
                # Use first numeric column
                numeric_cols = df.select_dtypes(include=['number']).columns
                column = numeric_cols[0] if len(numeric_cols) > 0 else df.columns[0]

        title = f'{column} Distribution'

        if chart_type in ['donut', 'pie', 'bar', 'horizontal_bar']:
            # Aggregate data
            value_counts = df[column].value_counts().head(limit)
            data = value_counts.values.tolist()
            labels = [str(label) for label in value_counts.index.tolist()]

        elif chart_type in ['line', 'area']:
            # For line charts, use sorted data
            if pd.api.types.is_datetime64_any_dtype(df.index):
                sorted_df = df.sort_index().head(limit)
                data = sorted_df[column].tolist()
                labels = [str(idx) for idx in sorted_df.index.tolist()]
            else:
                sorted_df = df.sort_values(column).head(limit)
                data = sorted_df[column].tolist()
                labels = [str(i) for i in range(len(data))]

        else:
            # Default: take first N rows
            data = df[column].head(limit).tolist()
            labels = [str(i) for i in range(len(data))]

        return data, labels, title
