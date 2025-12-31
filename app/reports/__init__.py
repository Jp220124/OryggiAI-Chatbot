"""
Report Generation Module
Handles PDF and Excel report generation for query results with charts and KPIs
"""

# Import xhtml2pdf PDF generator (Pure Python, Windows-friendly, no C dependencies)
# from .pdf_generator_playwright import Xhtml2PdfGenerator
from .excel_generator import ExcelReportGenerator
from .report_formatter import ReportFormatter
from .chart_generator import ChartGenerator
from .chart_selector import SmartChartSelector

# Optional: Import WeasyPrint PDF generator (requires GTK+ on Windows via MSYS2)
# Only available on systems with GTK+ properly installed
try:
    from .pdf_generator import PDFReportGenerator
    _WEASYPRINT_AVAILABLE = True
except (ImportError, OSError):
    PDFReportGenerator = None
    _WEASYPRINT_AVAILABLE = False

__all__ = [
    # "Xhtml2PdfGenerator",
    "ExcelReportGenerator",
    "ReportFormatter",
    "ChartGenerator",
    "SmartChartSelector"
]

# Add PDFReportGenerator to __all__ only if WeasyPrint is available
if _WEASYPRINT_AVAILABLE:
    __all__.append("PDFReportGenerator")
