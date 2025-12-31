"""
Report Generators Registry
Registers all report generators with the factory at application startup

This module provides a single function to initialize all report generators.
Call register_all_generators() at application startup to make generators available.
"""

from loguru import logger

from .generator_factory import report_generator_factory
from .excel_generator import ExcelReportGenerator


def register_all_generators() -> None:
    """
    Register all available report generators with the factory

    This should be called once at application startup (in app/main.py).

    Benefits:
    - Centralized registration (all generators registered in one place)
    - Easy to add new generators (just add registration line here)
    - Fails fast if generator doesn't implement interface properly
    """
    try:
        # Register Excel generator
        report_generator_factory.register(
            format_name='excel',
            generator_class=ExcelReportGenerator,
            singleton=True  # Reuse same instance for all Excel requests
        )
        logger.info("Registered Excel report generator")

        # Log available formats
        formats = report_generator_factory.list_formats()
        logger.success(f"Report generator factory initialized with formats: {formats}")

    except Exception as e:
        logger.error(f"Failed to register report generators: {str(e)}", exc_info=True)
        raise RuntimeError(f"Report generator registration failed: {str(e)}")
