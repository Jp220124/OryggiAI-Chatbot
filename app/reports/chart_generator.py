"""
Chart Generator Module
Generates professional charts as base64-encoded PNG images for PDF embedding
"""

import matplotlib
matplotlib.use('Agg')  # Non-GUI backend for server use
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from io import BytesIO
import base64
from typing import List, Dict, Any, Optional
import numpy as np


class ChartGenerator:
    """Generates charts as base64-encoded PNG images for PDF reports"""

    # Professional color scheme
    COLORS = {
        'primary': '#242c34',      # Navy Blue - headers, key metrics
        'secondary': '#5DA5DA',    # Light Blue - charts, accents
        'accent': '#FAA43A',       # Orange - highlights, warnings
        'success': '#5CB85C',      # Green - positive trends
        'danger': '#D9534F',       # Red - negative trends
        'neutral': '#60636A',      # Dark Grey
        'light_grey': '#F5F5F5',   # Light Grey background
        'white': '#FFFFFF'
    }

    # Chart color palettes
    CHART_COLORS = [
        '#5DA5DA',  # Light Blue
        '#FAA43A',  # Orange
        '#60BD68',  # Green
        '#F17CB0',  # Pink
        '#B2912F',  # Gold
        '#B276B2',  # Purple
        '#DECF3F',  # Yellow
        '#F15854',  # Red
    ]

    def __init__(self, color_scheme: Optional[Dict[str, str]] = None, dpi: int = 100):
        """
        Initialize chart generator

        Args:
            color_scheme: Custom color scheme (uses default if None)
            dpi: Image resolution (default: 100 for good quality/file size balance)
        """
        self.colors = color_scheme or self.COLORS
        self.dpi = dpi

        # Configure matplotlib defaults
        plt.rcParams['font.family'] = 'sans-serif'
        plt.rcParams['font.sans-serif'] = ['Arial', 'DejaVu Sans', 'Helvetica']
        plt.rcParams['font.size'] = 10
        plt.rcParams['axes.labelsize'] = 10
        plt.rcParams['axes.titlesize'] = 12
        plt.rcParams['xtick.labelsize'] = 9
        plt.rcParams['ytick.labelsize'] = 9
        plt.rcParams['legend.fontsize'] = 9

    def generate_pie_chart(
        self,
        data: List[float],
        labels: List[str],
        title: str = "",
        show_percentages: bool = True
    ) -> str:
        """
        Generate a pie chart

        Args:
            data: List of values
            labels: List of labels for each value
            title: Chart title
            show_percentages: Whether to show percentages on slices

        Returns:
            Base64-encoded PNG image string
        """
        fig, ax = plt.subplots(figsize=(7, 7))

        # Create pie chart
        autopct = '%1.1f%%' if show_percentages else None
        wedges, texts, autotexts = ax.pie(
            data,
            labels=labels,
            autopct=autopct,
            colors=self.CHART_COLORS[:len(data)],
            startangle=90,
            textprops={'fontsize': 10}
        )

        # Make percentage text white for better visibility
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_weight('bold')

        ax.set_title(title, fontsize=14, fontweight='bold', pad=20)

        return self._to_base64(fig)

    def generate_donut_chart(
        self,
        data: List[float],
        labels: List[str],
        title: str = "",
        show_percentages: bool = True,
        center_text: Optional[str] = None
    ) -> str:
        """
        Generate a donut chart (pie chart with hole in center)

        Args:
            data: List of values
            labels: List of labels for each value
            title: Chart title
            show_percentages: Whether to show percentages on slices
            center_text: Optional text to display in center

        Returns:
            Base64-encoded PNG image string
        """
        fig, ax = plt.subplots(figsize=(7, 7))

        # Create donut chart (pie with wedgeprops to create hole)
        autopct = '%1.1f%%' if show_percentages else None
        wedges, texts, autotexts = ax.pie(
            data,
            labels=labels,
            autopct=autopct,
            colors=self.CHART_COLORS[:len(data)],
            startangle=90,
            wedgeprops=dict(width=0.5, edgecolor='white'),  # Creates donut
            textprops={'fontsize': 10}
        )

        # Make percentage text visible
        for autotext in autotexts:
            autotext.set_color('white')
            autotext.set_weight('bold')

        # Add center text if provided
        if center_text:
            ax.text(0, 0, center_text, ha='center', va='center',
                   fontsize=16, fontweight='bold', color=self.colors['primary'])

        ax.set_title(title, fontsize=14, fontweight='bold', pad=20)

        return self._to_base64(fig)

    def generate_bar_chart(
        self,
        data: List[float],
        labels: List[str],
        title: str = "",
        xlabel: str = "",
        ylabel: str = "",
        horizontal: bool = False,
        show_values: bool = True
    ) -> str:
        """
        Generate a bar chart

        Args:
            data: List of values
            labels: List of labels for each bar
            title: Chart title
            xlabel: X-axis label
            ylabel: Y-axis label
            horizontal: If True, creates horizontal bars
            show_values: If True, displays values on bars

        Returns:
            Base64-encoded PNG image string
        """
        fig, ax = plt.subplots(figsize=(10, 6))

        if horizontal:
            bars = ax.barh(labels, data, color=self.colors['primary'])
            ax.set_xlabel(ylabel if ylabel else "Value")
            ax.set_ylabel(xlabel if xlabel else "")

            # Add value labels
            if show_values:
                for i, (bar, value) in enumerate(zip(bars, data)):
                    ax.text(value, i, f' {value:.0f}',
                           va='center', fontsize=9)
        else:
            bars = ax.bar(labels, data, color=self.colors['primary'])
            ax.set_xlabel(xlabel if xlabel else "")
            ax.set_ylabel(ylabel if ylabel else "Value")

            # Add value labels on top of bars
            if show_values:
                for bar in bars:
                    height = bar.get_height()
                    ax.text(bar.get_x() + bar.get_width()/2., height,
                           f'{height:.0f}',
                           ha='center', va='bottom', fontsize=9)

        ax.set_title(title, fontsize=14, fontweight='bold', pad=15)
        ax.grid(axis='x' if horizontal else 'y', alpha=0.3, linestyle='--')
        plt.tight_layout()

        return self._to_base64(fig)

    def generate_line_chart(
        self,
        x_data: List[Any],
        y_data: List[float],
        title: str = "",
        xlabel: str = "",
        ylabel: str = "",
        show_markers: bool = True,
        show_grid: bool = True
    ) -> str:
        """
        Generate a line chart

        Args:
            x_data: X-axis values (can be dates, numbers, strings)
            y_data: Y-axis values
            title: Chart title
            xlabel: X-axis label
            ylabel: Y-axis label
            show_markers: If True, shows markers on data points
            show_grid: If True, shows grid lines

        Returns:
            Base64-encoded PNG image string
        """
        fig, ax = plt.subplots(figsize=(10, 6))

        marker = 'o' if show_markers else None
        ax.plot(x_data, y_data, marker=marker, linewidth=2.5,
               color=self.colors['primary'], markersize=6,
               markerfacecolor=self.colors['secondary'],
               markeredgecolor=self.colors['primary'],
               markeredgewidth=1.5)

        ax.set_title(title, fontsize=14, fontweight='bold', pad=15)
        ax.set_xlabel(xlabel, fontsize=11)
        ax.set_ylabel(ylabel, fontsize=11)

        if show_grid:
            ax.grid(True, alpha=0.3, linestyle='--')

        # Rotate x-axis labels if they're long
        if any(len(str(x)) > 10 for x in x_data):
            plt.xticks(rotation=45, ha='right')

        plt.tight_layout()

        return self._to_base64(fig)

    def generate_multi_bar_chart(
        self,
        categories: List[str],
        datasets: List[Dict[str, Any]],
        title: str = "",
        xlabel: str = "",
        ylabel: str = "",
    ) -> str:
        """
        Generate a grouped bar chart with multiple datasets

        Args:
            categories: List of category labels
            datasets: List of dicts with 'label' and 'data' keys
                Example: [{'label': 'Series 1', 'data': [1, 2, 3]}, ...]
            title: Chart title
            xlabel: X-axis label
            ylabel: Y-axis label

        Returns:
            Base64-encoded PNG image string
        """
        fig, ax = plt.subplots(figsize=(12, 6))

        x = np.arange(len(categories))
        width = 0.8 / len(datasets)  # Width of bars

        for i, dataset in enumerate(datasets):
            offset = width * i - (width * (len(datasets) - 1) / 2)
            ax.bar(x + offset, dataset['data'], width,
                  label=dataset['label'],
                  color=self.CHART_COLORS[i % len(self.CHART_COLORS)])

        ax.set_title(title, fontsize=14, fontweight='bold', pad=15)
        ax.set_xlabel(xlabel, fontsize=11)
        ax.set_ylabel(ylabel, fontsize=11)
        ax.set_xticks(x)
        ax.set_xticklabels(categories)
        ax.legend()
        ax.grid(axis='y', alpha=0.3, linestyle='--')

        plt.tight_layout()

        return self._to_base64(fig)

    def generate_area_chart(
        self,
        x_data: List[Any],
        y_data: List[float],
        title: str = "",
        xlabel: str = "",
        ylabel: str = "",
        fill_alpha: float = 0.3
    ) -> str:
        """
        Generate an area chart

        Args:
            x_data: X-axis values
            y_data: Y-axis values
            title: Chart title
            xlabel: X-axis label
            ylabel: Y-axis label
            fill_alpha: Transparency of filled area (0-1)

        Returns:
            Base64-encoded PNG image string
        """
        fig, ax = plt.subplots(figsize=(10, 6))

        ax.plot(x_data, y_data, linewidth=2, color=self.colors['primary'])
        ax.fill_between(x_data, y_data, alpha=fill_alpha,
                        color=self.colors['secondary'])

        ax.set_title(title, fontsize=14, fontweight='bold', pad=15)
        ax.set_xlabel(xlabel, fontsize=11)
        ax.set_ylabel(ylabel, fontsize=11)
        ax.grid(True, alpha=0.3, linestyle='--')

        if any(len(str(x)) > 10 for x in x_data):
            plt.xticks(rotation=45, ha='right')

        plt.tight_layout()

        return self._to_base64(fig)

    def _to_base64(self, fig) -> str:
        """
        Convert matplotlib figure to base64-encoded PNG string

        Args:
            fig: Matplotlib figure object

        Returns:
            Base64-encoded data URI string
        """
        buffer = BytesIO()
        fig.savefig(buffer, format='png', dpi=self.dpi,
                   bbox_inches='tight', facecolor='white', edgecolor='none')
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.read()).decode('utf-8')
        plt.close(fig)  # Important: free memory

        return f"data:image/png;base64,{image_base64}"

    def close_all(self):
        """Close all matplotlib figures to free memory"""
        plt.close('all')
