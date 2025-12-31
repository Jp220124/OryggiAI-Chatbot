"""
Report Generator Factory
Implements Factory Pattern for creating and managing report generators

Benefits:
- Centralized registration of all generators (no hardcoded imports)
- Easy to add new generators without modifying existing code
- Supports runtime configuration and dependency injection
- Enables true microservices architecture (components can be swapped independently)
"""

from typing import Dict, Type, Optional
from loguru import logger

from .interfaces import ReportGenerator


class ReportGeneratorFactory:
    """
    Factory for creating report generators

    Usage:
        # Register generators (typically done at startup)
        factory.register('pdf', WeasyPrintGenerator)
        factory.register('excel', ExcelReportGenerator)

        # Get generator instance
        pdf_gen = factory.get('pdf')
        excel_gen = factory.get('excel')

    Benefits:
        - Open/Closed Principle: Add new generators without modifying factory
        - Dependency Inversion: Callers depend on factory, not concrete classes
        - Single Responsibility: Factory manages generator lifecycle
    """

    def __init__(self):
        """Initialize empty factory"""
        self._generators: Dict[str, Type[ReportGenerator]] = {}
        self._instances: Dict[str, ReportGenerator] = {}
        logger.debug("ReportGeneratorFactory initialized")

    def register(
        self,
        format_name: str,
        generator_class: Type[ReportGenerator],
        singleton: bool = True
    ) -> None:
        """
        Register a report generator

        Args:
            format_name: Format identifier (e.g., 'pdf', 'excel', 'csv')
            generator_class: Class that implements ReportGenerator interface
            singleton: If True, reuse same instance (default: True)

        Raises:
            ValueError: If format_name is already registered
            TypeError: If generator_class doesn't implement ReportGenerator

        Example:
            factory.register('pdf', WeasyPrintGenerator)
            factory.register('excel', ExcelReportGenerator)
        """
        format_name = format_name.lower()

        # Validate generator implements interface
        if not issubclass(generator_class, ReportGenerator):
            raise TypeError(
                f"Generator class {generator_class.__name__} must implement ReportGenerator interface"
            )

        # Check if already registered
        if format_name in self._generators:
            logger.warning(
                f"Format '{format_name}' already registered with {self._generators[format_name].__name__}. "
                f"Replacing with {generator_class.__name__}"
            )

        self._generators[format_name] = generator_class

        # Create singleton instance if requested
        if singleton:
            self._instances[format_name] = generator_class()
            logger.info(
                f"Registered singleton generator '{format_name}': {generator_class.__name__}"
            )
        else:
            logger.info(
                f"Registered generator '{format_name}': {generator_class.__name__} (new instance per request)"
            )

    def unregister(self, format_name: str) -> None:
        """
        Unregister a report generator

        Args:
            format_name: Format identifier to remove

        Example:
            factory.unregister('pdf')  # Remove PDF generator
        """
        format_name = format_name.lower()

        if format_name in self._generators:
            del self._generators[format_name]
            logger.info(f"Unregistered generator '{format_name}'")

        if format_name in self._instances:
            del self._instances[format_name]

    def get(self, format_name: str) -> ReportGenerator:
        """
        Get report generator instance

        Args:
            format_name: Format identifier (e.g., 'pdf', 'excel')

        Returns:
            ReportGenerator instance

        Raises:
            ValueError: If format_name is not registered

        Example:
            pdf_gen = factory.get('pdf')
            report_path = await pdf_gen.generate_table_report(...)
        """
        format_name = format_name.lower()

        if format_name not in self._generators:
            available = ', '.join(self._generators.keys())
            raise ValueError(
                f"Unknown report format '{format_name}'. "
                f"Available formats: {available or 'none'}"
            )

        # Return singleton instance if available
        if format_name in self._instances:
            return self._instances[format_name]

        # Create new instance
        generator_class = self._generators[format_name]
        return generator_class()

    def list_formats(self) -> list:
        """
        List all registered format names

        Returns:
            List of format identifiers

        Example:
            formats = factory.list_formats()
            # ['pdf', 'excel', 'csv']
        """
        return list(self._generators.keys())

    def has_format(self, format_name: str) -> bool:
        """
        Check if format is registered

        Args:
            format_name: Format identifier to check

        Returns:
            True if format is registered

        Example:
            if factory.has_format('pdf'):
                pdf_gen = factory.get('pdf')
        """
        return format_name.lower() in self._generators

    def clear(self) -> None:
        """
        Clear all registered generators (useful for testing)

        Example:
            factory.clear()
        """
        self._generators.clear()
        self._instances.clear()
        logger.debug("Cleared all registered generators")


# Global factory instance (initialized at startup)
report_generator_factory = ReportGeneratorFactory()
