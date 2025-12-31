"""
Onboarding Orchestrator
Coordinates the entire automatic onboarding process
User just provides connection string -> System does EVERYTHING automatically

ENHANCED: Now includes DataContextDetector for intelligent organization identification
- Analyzes actual DATA content, not just schema structure
- Identifies organization name (e.g., "MUJ University" not just "HR System")
- Detects organization type from data patterns (University vs Coal Mine vs Metro)
- Generates domain-specific few-shot examples
"""

import asyncio
import uuid
from typing import Dict, Any, Optional, Callable, Awaitable
from datetime import datetime
from loguru import logger

from .schema_extractor import AutoSchemaExtractor
from .llm_analyzer import LLMSchemaAnalyzer
from .fewshot_generator import AutoFewShotGenerator
from .auto_embedder import AutoEmbedder
from .data_context_detector import DataContextDetector  # NEW: Data-driven context detection


class OnboardingOrchestrator:
    """
    Master orchestrator for automatic database onboarding

    THE MAGIC:
    User provides: Connection string
    System does:
        1. Extract full database schema (tables, views, columns, relationships)
        2. LLM analyzes schema to understand organization type
        3. Auto-generate 50+ relevant Q&A pairs
        4. Create ChromaDB embeddings for RAG
        5. Ready to chat!

    Zero manual configuration required.
    """

    def __init__(self):
        """Initialize all sub-components"""
        self.analyzer = LLMSchemaAnalyzer()
        self.fewshot_gen = AutoFewShotGenerator()
        self.embedder = AutoEmbedder()
        logger.info("OnboardingOrchestrator initialized")

    async def onboard_database(
        self,
        connection_string: str,
        tenant_id: Optional[str] = None,
        tenant_name: Optional[str] = None,
        db_schema: str = "dbo",
        fewshot_count: int = 50,
        include_views: bool = True,
        max_tables: Optional[int] = None,
        progress_callback: Optional[Callable[[str, int], Awaitable[None]]] = None
    ) -> Dict[str, Any]:
        """
        Complete automatic onboarding - user just provides connection string

        Args:
            connection_string: SQLAlchemy-compatible connection string
            tenant_id: Optional tenant ID (auto-generated if not provided)
            tenant_name: Optional tenant name
            db_schema: Database schema (default: dbo)
            fewshot_count: Number of few-shot examples to generate (default: 50)
            include_views: Include database views (default: True)
            max_tables: Limit tables extracted (for testing)
            progress_callback: Optional async callback for progress updates
                               Signature: async def callback(step: str, progress: int)

        Returns:
            {
                "success": True/False,
                "tenant_id": "unique-tenant-id",
                "organization_type": "Access Control System",
                "organization_description": "...",
                "detected_modules": ["Employee Management", "Access Control", ...],
                "tables_analyzed": 50,
                "views_analyzed": 15,
                "fewshots_generated": 50,
                "embeddings_created": 100,
                "collection_ids": {
                    "schema": "tenant_xxx_schema",
                    "fewshots": "tenant_xxx_fewshots"
                },
                "steps_completed": ["schema_extraction", "llm_analysis", ...],
                "errors": [],
                "ready_to_chat": True,
                "onboarding_time_seconds": 120
            }
        """
        start_time = datetime.now()
        tenant_id = tenant_id or str(uuid.uuid4())[:8]

        result = {
            "success": False,
            "tenant_id": tenant_id,
            "tenant_name": tenant_name,
            # Organization identification (NEW - from DataContextDetector)
            "organization_name": None,  # Actual org name like "MUJ University"
            "organization_type": None,  # Type code like "university", "coal_mine"
            "organization_type_display": None,  # Human readable like "University / Educational Institution"
            "detection_confidence": 0.0,  # How confident the detection is
            "domain_vocabulary": {},  # Domain-specific terms
            "key_entities": [],  # Key business entities
            # Schema analysis
            "organization_description": None,
            "detected_modules": [],
            "tables_analyzed": 0,
            "views_analyzed": 0,
            # Generation results
            "fewshots_generated": 0,
            "embeddings_created": 0,
            "collection_ids": {},
            # Status
            "steps_completed": [],
            "errors": [],
            "ready_to_chat": False,
            "onboarding_time_seconds": 0
        }

        async def update_progress(step: str, progress: int):
            """Helper to update progress"""
            if progress_callback:
                try:
                    await progress_callback(step, progress)
                except Exception:
                    pass
            logger.info(f"[{progress}%] {step}")

        try:
            # =========================================================
            # STEP 1: EXTRACT DATABASE SCHEMA (Automatic)
            # =========================================================
            await update_progress("Connecting to database...", 5)

            extractor = AutoSchemaExtractor(connection_string)
            extractor.connect()

            await update_progress("Extracting database schema...", 10)

            schema = await extractor.extract_full_schema(
                schema=db_schema,
                include_views=include_views,
                sample_rows=5,
                max_tables=max_tables
            )

            result["tables_analyzed"] = len(schema.get("tables", {}))
            result["views_analyzed"] = len(schema.get("views", {}))
            result["steps_completed"].append("schema_extraction")

            await update_progress(
                f"Found {result['tables_analyzed']} tables, {result['views_analyzed']} views",
                20
            )

            # =========================================================
            # STEP 2: DATA CONTEXT DETECTION (NEW - The Magic!)
            # =========================================================
            await update_progress("Analyzing organization data...", 25)

            context_detector = DataContextDetector(connection_string)
            org_context = await context_detector.detect_context(schema)

            # Store organization context in result
            result["organization_name"] = org_context.get("organization_name", "Unknown")
            result["organization_type"] = org_context.get("organization_type", "corporate")
            result["organization_type_display"] = org_context.get("organization_type_display", "Organization")
            result["detection_confidence"] = org_context.get("confidence", 0.0)
            result["domain_vocabulary"] = org_context.get("domain_vocabulary", {})
            result["key_entities"] = org_context.get("key_entities", [])
            result["steps_completed"].append("data_context_detection")

            await update_progress(
                f"Detected: {result['organization_name']} ({result['organization_type_display']})",
                35
            )

            logger.info(f"Organization detected: {result['organization_name']}")
            logger.info(f"Type: {result['organization_type']} (confidence: {result['detection_confidence']:.2%})")

            # =========================================================
            # STEP 3: LLM ANALYZES SCHEMA (Enhanced with context)
            # =========================================================
            await update_progress("AI analyzing database structure...", 40)

            analysis = await self.analyzer.analyze_schema(schema)

            # Merge LLM analysis with data context (data context takes priority for org info)
            result["organization_description"] = analysis.get("organization_description", "")
            result["detected_modules"] = analysis.get("detected_modules", [])
            result["steps_completed"].append("llm_analysis")

            await update_progress(
                f"Detected: {result['organization_type']} with {len(result['detected_modules'])} modules",
                45
            )

            # =========================================================
            # STEP 4: GENERATE FEW-SHOT EXAMPLES (Domain-Aware)
            # =========================================================
            await update_progress("Generating domain-specific Q&A examples...", 55)

            few_shots = await self.fewshot_gen.generate_fewshots(
                schema=schema,
                analysis=analysis,
                count=fewshot_count,
                org_context=org_context  # NEW: Pass organization context for domain-specific questions
            )

            result["fewshots_generated"] = len(few_shots)
            result["steps_completed"].append("fewshot_generation")

            await update_progress(
                f"Generated {result['fewshots_generated']} Q&A examples",
                70
            )

            # =========================================================
            # STEP 5: CREATE EMBEDDINGS (Automatic)
            # =========================================================
            await update_progress("Creating knowledge base...", 80)

            embedding_result = await self.embedder.create_tenant_embeddings(
                tenant_id=tenant_id,
                schema=schema,
                analysis=analysis,
                few_shots=few_shots
            )

            result["collection_ids"] = {
                "schema": embedding_result["schema_collection"],
                "fewshots": embedding_result["fewshot_collection"]
            }
            result["embeddings_created"] = (
                embedding_result["schema_count"] + embedding_result["fewshot_count"]
            )
            result["steps_completed"].append("embedding_creation")

            await update_progress(
                f"Created {result['embeddings_created']} embeddings",
                95
            )

            # =========================================================
            # SUCCESS!
            # =========================================================
            result["success"] = True
            result["ready_to_chat"] = True

            end_time = datetime.now()
            result["onboarding_time_seconds"] = (end_time - start_time).total_seconds()

            await update_progress(
                f"Onboarding complete! Ready to chat in {result['onboarding_time_seconds']:.1f}s",
                100
            )

            logger.info(f"Onboarding successful for tenant {tenant_id}")
            logger.info(f"  Organization: {result['organization_type']}")
            logger.info(f"  Modules: {result['detected_modules']}")
            logger.info(f"  Tables: {result['tables_analyzed']}")
            logger.info(f"  Few-shots: {result['fewshots_generated']}")
            logger.info(f"  Time: {result['onboarding_time_seconds']:.1f}s")

            # Clean up
            extractor.close()
            context_detector.close()

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Onboarding failed: {error_msg}")
            result["errors"].append(error_msg)

            if progress_callback:
                try:
                    await progress_callback(f"Error: {error_msg}", -1)
                except Exception:
                    pass

        return result

    async def test_connection(self, connection_string: str) -> Dict[str, Any]:
        """
        Test database connection before full onboarding

        Args:
            connection_string: SQLAlchemy connection string

        Returns:
            {
                "success": True/False,
                "message": "Connection successful" or error message,
                "db_type": "mssql/postgresql/mysql",
                "tables_found": 50
            }
        """
        try:
            extractor = AutoSchemaExtractor(connection_string)
            extractor.connect()

            # Quick table count
            tables = extractor._get_tables("dbo")

            return {
                "success": True,
                "message": "Connection successful",
                "db_type": extractor.db_type,
                "tables_found": len(tables)
            }

        except Exception as e:
            return {
                "success": False,
                "message": str(e),
                "db_type": None,
                "tables_found": 0
            }

    def get_tenant_status(self, tenant_id: str) -> Dict[str, Any]:
        """
        Check status of tenant's onboarding

        Returns:
            {
                "initialized": True/False,
                "schema_count": 50,
                "fewshot_count": 50,
                "ready_to_chat": True/False
            }
        """
        stats = self.embedder.get_collection_stats(tenant_id)

        return {
            "initialized": stats["schema_count"] > 0,
            "schema_count": stats["schema_count"],
            "fewshot_count": stats["fewshot_count"],
            "ready_to_chat": stats["schema_count"] > 0 and stats["fewshot_count"] > 0
        }

    def delete_tenant(self, tenant_id: str):
        """
        Delete all data for a tenant

        Args:
            tenant_id: Tenant identifier
        """
        logger.info(f"Deleting tenant: {tenant_id}")
        self.embedder.delete_tenant_collections(tenant_id)


# Singleton instance for easy access
onboarding_orchestrator = OnboardingOrchestrator()


# Convenience function for external use
async def auto_onboard(
    connection_string: str,
    tenant_id: Optional[str] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    Convenience function for automatic onboarding

    Usage:
        result = await auto_onboard(
            "mssql+pyodbc://user:pass@server/db?driver=ODBC+Driver+17+for+SQL+Server"
        )
        if result["success"]:
            print(f"Ready! Organization: {result['organization_type']}")
    """
    return await onboarding_orchestrator.onboard_database(
        connection_string=connection_string,
        tenant_id=tenant_id,
        **kwargs
    )
