"""
Tenant Onboarding Service
Integrates auto-onboarding with multi-tenant platform database

This service:
1. Runs auto-onboarding for a tenant's database
2. Stores SchemaCache records in platform DB
3. Stores FewShotExample records in platform DB
4. Updates TenantDatabase.schema_analyzed flag

GATEWAY MODE:
For databases behind firewalls (connection_mode='gateway_only'), this service
uses the GatewaySchemaExtractor to extract schema through the Gateway Agent
WebSocket connection instead of direct database connections.
"""

import json
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List
from urllib.parse import quote_plus
from loguru import logger
from sqlalchemy.orm import Session

from app.models.platform import TenantDatabase, SchemaCache, FewShotExample
from app.services.auto_onboarding import OnboardingOrchestrator
from app.services.auto_onboarding.gateway_schema_extractor import GatewaySchemaExtractor
from app.gateway.connection_manager import gateway_manager
from app.security.encryption import decrypt_string


class TenantOnboardingService:
    """
    Service for onboarding tenant databases with platform DB integration

    Supports two modes:
    1. Direct mode: Uses SQLAlchemy connection strings for direct DB access
    2. Gateway mode: Uses Gateway Agent WebSocket for firewalled databases
    """

    def __init__(self):
        self.orchestrator = OnboardingOrchestrator()

    def _should_use_gateway(self, tenant_database: TenantDatabase) -> bool:
        """
        Determine if we should use Gateway Agent for this database.

        Uses gateway if:
        - connection_mode is 'gateway_only' OR
        - Gateway Agent is currently connected (gateway_connected=True)
        """
        # Check connection mode
        if hasattr(tenant_database, 'connection_mode'):
            if tenant_database.connection_mode == 'gateway_only':
                return True

        # Check if gateway is currently connected
        if tenant_database.gateway_connected:
            # Also verify the agent is actually connected in memory
            database_id = str(tenant_database.id)
            if gateway_manager.is_connected(database_id):
                return True

        return False

    async def onboard_tenant_database(
        self,
        db: Session,
        tenant_database: TenantDatabase,
        fewshot_count: int = 50,
        include_views: bool = True,
        progress_callback=None
    ) -> Dict[str, Any]:
        """
        Onboard a tenant's database with full platform integration

        Args:
            db: SQLAlchemy session for platform database
            tenant_database: TenantDatabase model instance
            fewshot_count: Number of few-shot examples to generate
            include_views: Include database views
            progress_callback: Optional progress callback

        Returns:
            Onboarding result with success status and details
        """
        tenant_id = str(tenant_database.tenant_id)
        tenant_db_id = tenant_database.id

        logger.info(f"Starting onboarding for tenant database: {tenant_database.name}")

        # Check if we should use Gateway Agent mode
        use_gateway = self._should_use_gateway(tenant_database)
        database_id = str(tenant_database.id)

        if use_gateway:
            logger.info(f"Using Gateway Agent mode for database {tenant_database.name}")
            if not gateway_manager.is_connected(database_id):
                raise Exception(
                    f"Gateway Agent not connected for database {tenant_database.name}. "
                    "Please ensure the Gateway Agent is running and connected."
                )
        else:
            logger.info(f"Using direct connection mode for database {tenant_database.name}")

        result = {
            "success": False,
            "tenant_db_id": str(tenant_db_id),
            "tenant_id": tenant_id,
            "schema_records": 0,
            "fewshot_records": 0,
            "errors": [],
            "mode": "gateway" if use_gateway else "direct"
        }

        try:
            if use_gateway:
                # =========================================================
                # GATEWAY MODE: Extract schema through Gateway Agent
                # =========================================================
                onboard_result = await self._onboard_via_gateway(
                    tenant_database=tenant_database,
                    tenant_id=tenant_id,
                    fewshot_count=fewshot_count,
                    include_views=include_views,
                    progress_callback=progress_callback
                )
            else:
                # =========================================================
                # DIRECT MODE: Use standard SQLAlchemy connection
                # =========================================================
                connection_string = self._build_connection_string(tenant_database)
                onboard_result = await self.orchestrator.onboard_database(
                    connection_string=connection_string,
                    tenant_id=tenant_id,
                    tenant_name=tenant_database.name,
                    db_schema="dbo",
                    fewshot_count=fewshot_count,
                    include_views=include_views,
                    progress_callback=progress_callback
                )

            if not onboard_result["success"]:
                result["errors"] = onboard_result.get("errors", ["Onboarding failed"])
                return result

            # Step 2: Store schema cache in platform DB
            # For gateway mode, schema is already in onboard_result
            if use_gateway:
                schema_records = await self._store_schema_cache_from_result(
                    db=db,
                    tenant_db_id=tenant_db_id,
                    onboard_result=onboard_result
                )
            else:
                connection_string = self._build_connection_string(tenant_database)
                schema_records = await self._store_schema_cache(
                    db=db,
                    tenant_db_id=tenant_db_id,
                    onboard_result=onboard_result,
                    connection_string=connection_string
                )
            result["schema_records"] = schema_records

            # Step 3: Store few-shot examples in platform DB
            if use_gateway:
                fewshot_records = await self._store_fewshot_examples_from_result(
                    db=db,
                    tenant_db_id=tenant_db_id,
                    onboard_result=onboard_result
                )
            else:
                fewshot_records = await self._store_fewshot_examples(
                    db=db,
                    tenant_db_id=tenant_db_id,
                    onboard_result=onboard_result,
                    connection_string=connection_string
                )
            result["fewshot_records"] = fewshot_records

            # Step 4: Update tenant database status
            tenant_database.schema_analyzed = True
            tenant_database.analysis_status = "completed"
            tenant_database.table_count = onboard_result.get("tables_analyzed", 0)
            tenant_database.view_count = onboard_result.get("views_analyzed", 0)
            tenant_database.detected_organization_type = onboard_result.get("organization_type")
            tenant_database.detected_modules = json.dumps(onboard_result.get("detected_modules", []))
            tenant_database.last_connected_at = datetime.utcnow()
            tenant_database.last_analysis_at = datetime.utcnow()
            db.commit()

            # Copy relevant info from onboard_result
            result["success"] = True
            result["organization_name"] = onboard_result.get("organization_name")
            result["organization_type"] = onboard_result.get("organization_type")
            result["organization_type_display"] = onboard_result.get("organization_type_display")
            result["detected_modules"] = onboard_result.get("detected_modules", [])
            result["tables_analyzed"] = onboard_result.get("tables_analyzed", 0)
            result["views_analyzed"] = onboard_result.get("views_analyzed", 0)
            result["collection_ids"] = onboard_result.get("collection_ids", {})
            result["onboarding_time_seconds"] = onboard_result.get("onboarding_time_seconds", 0)

            logger.info(f"Onboarding complete for {tenant_database.name}")
            logger.info(f"  Schema records: {schema_records}")
            logger.info(f"  Few-shot records: {fewshot_records}")

        except Exception as e:
            logger.error(f"Tenant onboarding failed: {str(e)}")
            result["errors"].append(str(e))
            db.rollback()

        return result

    async def _store_schema_cache(
        self,
        db: Session,
        tenant_db_id: uuid.UUID,
        onboard_result: Dict[str, Any],
        connection_string: str
    ) -> int:
        """
        Store extracted schema in platform database

        Returns number of records stored
        """
        from app.services.auto_onboarding.schema_extractor import AutoSchemaExtractor

        try:
            # Re-extract schema for detailed storage
            extractor = AutoSchemaExtractor(connection_string)
            extractor.connect()

            schema = await extractor.extract_full_schema(
                schema="dbo",
                include_views=True,
                sample_rows=5
            )

            records_created = 0

            # Clear existing schema cache for this database
            db.query(SchemaCache).filter(
                SchemaCache.tenant_db_id == tenant_db_id
            ).delete()

            # Store tables
            for table_name, table_info in schema.get("tables", {}).items():
                schema_cache = SchemaCache(
                    tenant_db_id=tenant_db_id,
                    table_name=table_name,
                    schema_name="dbo",
                    table_type="table",
                    column_info=json.dumps(table_info.get("columns", [])),
                    sample_data=json.dumps(table_info.get("sample_data", [])[:5]),
                    row_count=table_info.get("row_count", 0),
                    column_count=len(table_info.get("columns", [])),
                    llm_description=onboard_result.get("organization_description"),
                    detected_module=self._detect_module_for_table(
                        table_name,
                        onboard_result.get("detected_modules", [])
                    ),
                    foreign_keys=json.dumps(table_info.get("foreign_keys", []))
                )
                db.add(schema_cache)
                records_created += 1

            # Store views
            for view_name, view_info in schema.get("views", {}).items():
                schema_cache = SchemaCache(
                    tenant_db_id=tenant_db_id,
                    table_name=view_name,
                    schema_name="dbo",
                    table_type="view",
                    column_info=json.dumps(view_info.get("columns", [])),
                    sample_data=json.dumps(view_info.get("sample_data", [])[:5]),
                    row_count=view_info.get("row_count", 0),
                    column_count=len(view_info.get("columns", []))
                )
                db.add(schema_cache)
                records_created += 1

            db.commit()
            extractor.close()

            return records_created

        except Exception as e:
            logger.error(f"Failed to store schema cache: {str(e)}")
            raise

    async def _store_fewshot_examples(
        self,
        db: Session,
        tenant_db_id: uuid.UUID,
        onboard_result: Dict[str, Any],
        connection_string: str
    ) -> int:
        """
        Store generated few-shot examples in platform database

        Returns number of records stored
        """
        from app.services.auto_onboarding.schema_extractor import AutoSchemaExtractor
        from app.services.auto_onboarding.fewshot_generator import AutoFewShotGenerator

        try:
            # Re-extract schema
            extractor = AutoSchemaExtractor(connection_string)
            extractor.connect()

            schema = await extractor.extract_full_schema(
                schema="dbo",
                include_views=True,
                sample_rows=3
            )

            # Build analysis object from onboard_result
            analysis = {
                "organization_type": onboard_result.get("organization_type", "corporate"),
                "detected_modules": onboard_result.get("detected_modules", []),
                "organization_description": onboard_result.get("organization_description", ""),
                "table_descriptions": {}
            }

            # Build org_context from onboard_result
            org_context = {
                "organization_name": onboard_result.get("organization_name", "Unknown"),
                "organization_type": onboard_result.get("organization_type", "corporate"),
                "organization_type_display": onboard_result.get("organization_type_display", "Organization"),
                "confidence": onboard_result.get("detection_confidence", 0.5),
                "domain_vocabulary": onboard_result.get("domain_vocabulary", {}),
                "key_entities": onboard_result.get("key_entities", [])
            }

            # Generate few-shots
            fewshot_gen = AutoFewShotGenerator()
            few_shots = await fewshot_gen.generate_fewshots(
                schema=schema,
                analysis=analysis,
                count=50,
                org_context=org_context
            )

            # Clear existing few-shot examples for this database
            db.query(FewShotExample).filter(
                FewShotExample.tenant_db_id == tenant_db_id
            ).delete()

            records_created = 0

            for fs in few_shots:
                fewshot_record = FewShotExample(
                    tenant_db_id=tenant_db_id,
                    question=fs.get("question", ""),
                    sql_query=fs.get("sql", ""),
                    explanation=fs.get("explanation"),
                    module=fs.get("module"),
                    category=fs.get("category"),
                    complexity=fs.get("complexity", "medium"),
                    tables_used=json.dumps(fs.get("tables", [])),
                    is_verified=False,
                    is_active=True,
                    source="auto",
                    generated_by="gpt-4"
                )
                db.add(fewshot_record)
                records_created += 1

            db.commit()
            extractor.close()

            return records_created

        except Exception as e:
            logger.error(f"Failed to store few-shot examples: {str(e)}")
            raise

    async def _onboard_via_gateway(
        self,
        tenant_database: TenantDatabase,
        tenant_id: str,
        fewshot_count: int = 50,
        include_views: bool = True,
        progress_callback=None
    ) -> Dict[str, Any]:
        """
        Perform onboarding through Gateway Agent WebSocket connection.

        This is used for databases behind firewalls that cannot be accessed
        directly by the SaaS platform.
        """
        from app.services.auto_onboarding.llm_analyzer import LLMSchemaAnalyzer
        from app.services.auto_onboarding.fewshot_generator import AutoFewShotGenerator
        from app.services.auto_onboarding.auto_embedder import AutoEmbedder

        database_id = str(tenant_database.id)
        db_type = tenant_database.db_type.lower() if tenant_database.db_type else "mssql"
        start_time = datetime.utcnow()

        result = {
            "success": False,
            "tenant_id": tenant_id,
            "tenant_name": tenant_database.name,
            "organization_name": None,
            "organization_type": None,
            "organization_type_display": None,
            "detection_confidence": 0.0,
            "domain_vocabulary": {},
            "key_entities": [],
            "organization_description": None,
            "detected_modules": [],
            "tables_analyzed": 0,
            "views_analyzed": 0,
            "fewshots_generated": 0,
            "embeddings_created": 0,
            "collection_ids": {},
            "steps_completed": [],
            "errors": [],
            "ready_to_chat": False,
            "onboarding_time_seconds": 0,
            # Store schema for later use
            "schema": None,
            "few_shots": []
        }

        async def update_progress(step: str, progress: int):
            if progress_callback:
                try:
                    await progress_callback(step, progress)
                except Exception:
                    pass
            logger.info(f"[Gateway] [{progress}%] {step}")

        try:
            # =========================================================
            # STEP 1: EXTRACT SCHEMA VIA GATEWAY
            # =========================================================
            await update_progress("Connecting via Gateway Agent...", 5)

            extractor = GatewaySchemaExtractor(database_id, db_type)

            if not extractor.is_connected():
                raise Exception(f"Gateway Agent not connected for database {database_id}")

            await update_progress("Extracting database schema via gateway...", 10)

            schema = await extractor.extract_full_schema(
                schema="dbo",
                include_views=include_views,
                sample_rows=5
            )

            result["tables_analyzed"] = len(schema.get("tables", {}))
            result["views_analyzed"] = len(schema.get("views", {}))
            result["schema"] = schema  # Store for later
            result["steps_completed"].append("schema_extraction")

            await update_progress(
                f"Found {result['tables_analyzed']} tables, {result['views_analyzed']} views",
                25
            )

            # =========================================================
            # STEP 2: LLM ANALYZES SCHEMA
            # =========================================================
            await update_progress("AI analyzing database structure...", 35)

            analyzer = LLMSchemaAnalyzer()
            analysis = await analyzer.analyze_schema(schema)

            result["organization_description"] = analysis.get("organization_description", "")
            result["detected_modules"] = analysis.get("detected_modules", [])
            result["organization_type"] = analysis.get("organization_type", "corporate")
            result["organization_name"] = tenant_database.name
            result["organization_type_display"] = analysis.get("organization_type", "Organization")
            result["steps_completed"].append("llm_analysis")

            await update_progress(
                f"Detected: {result['organization_type']} with {len(result['detected_modules'])} modules",
                50
            )

            # =========================================================
            # STEP 3: GENERATE FEW-SHOT EXAMPLES
            # =========================================================
            await update_progress("Generating domain-specific Q&A examples...", 60)

            org_context = {
                "organization_name": result["organization_name"],
                "organization_type": result["organization_type"],
                "organization_type_display": result["organization_type_display"],
                "confidence": 0.8,
                "domain_vocabulary": {},
                "key_entities": []
            }

            fewshot_gen = AutoFewShotGenerator()
            few_shots = await fewshot_gen.generate_fewshots(
                schema=schema,
                analysis=analysis,
                count=fewshot_count,
                org_context=org_context
            )

            result["fewshots_generated"] = len(few_shots)
            result["few_shots"] = few_shots  # Store for later
            result["steps_completed"].append("fewshot_generation")

            await update_progress(
                f"Generated {result['fewshots_generated']} Q&A examples",
                75
            )

            # =========================================================
            # STEP 4: CREATE EMBEDDINGS
            # =========================================================
            await update_progress("Creating knowledge base...", 85)

            embedder = AutoEmbedder()
            embedding_result = await embedder.create_tenant_embeddings(
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

            end_time = datetime.utcnow()
            result["onboarding_time_seconds"] = (end_time - start_time).total_seconds()

            await update_progress(
                f"Gateway onboarding complete in {result['onboarding_time_seconds']:.1f}s",
                100
            )

            logger.info(f"Gateway onboarding successful for {tenant_database.name}")

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Gateway onboarding failed: {error_msg}")
            result["errors"].append(error_msg)

        return result

    async def _store_schema_cache_from_result(
        self,
        db: Session,
        tenant_db_id: uuid.UUID,
        onboard_result: Dict[str, Any]
    ) -> int:
        """
        Store schema cache from onboard_result (for gateway mode).
        Schema was already extracted during _onboard_via_gateway.
        """
        try:
            schema = onboard_result.get("schema", {})
            if not schema:
                logger.warning("No schema found in onboard_result")
                return 0

            records_created = 0

            # Clear existing schema cache for this database
            db.query(SchemaCache).filter(
                SchemaCache.tenant_db_id == tenant_db_id
            ).delete()

            # Store tables
            for table_name, table_info in schema.get("tables", {}).items():
                schema_cache = SchemaCache(
                    tenant_db_id=tenant_db_id,
                    table_name=table_name,
                    schema_name="dbo",
                    table_type="table",
                    column_info=json.dumps(table_info.get("columns", [])),
                    sample_data=json.dumps(table_info.get("sample_data", [])[:5]),
                    row_count=table_info.get("row_count", 0),
                    column_count=len(table_info.get("columns", [])),
                    llm_description=onboard_result.get("organization_description"),
                    detected_module=self._detect_module_for_table(
                        table_name,
                        onboard_result.get("detected_modules", [])
                    ),
                    foreign_keys=json.dumps(table_info.get("foreign_keys", []))
                )
                db.add(schema_cache)
                records_created += 1

            # Store views
            for view_name, view_info in schema.get("views", {}).items():
                schema_cache = SchemaCache(
                    tenant_db_id=tenant_db_id,
                    table_name=view_name,
                    schema_name="dbo",
                    table_type="view",
                    column_info=json.dumps(view_info.get("columns", [])),
                    sample_data=json.dumps(view_info.get("sample_data", [])[:5]),
                    row_count=view_info.get("row_count", 0),
                    column_count=len(view_info.get("columns", []))
                )
                db.add(schema_cache)
                records_created += 1

            db.commit()
            return records_created

        except Exception as e:
            logger.error(f"Failed to store schema cache from result: {str(e)}")
            raise

    async def _store_fewshot_examples_from_result(
        self,
        db: Session,
        tenant_db_id: uuid.UUID,
        onboard_result: Dict[str, Any]
    ) -> int:
        """
        Store few-shot examples from onboard_result (for gateway mode).
        Few-shots were already generated during _onboard_via_gateway.
        """
        try:
            few_shots = onboard_result.get("few_shots", [])
            if not few_shots:
                logger.warning("No few_shots found in onboard_result")
                return 0

            # Clear existing few-shot examples for this database
            db.query(FewShotExample).filter(
                FewShotExample.tenant_db_id == tenant_db_id
            ).delete()

            records_created = 0

            for fs in few_shots:
                fewshot_record = FewShotExample(
                    tenant_db_id=tenant_db_id,
                    question=fs.get("question", ""),
                    sql_query=fs.get("sql", ""),
                    explanation=fs.get("explanation"),
                    module=fs.get("module"),
                    category=fs.get("category"),
                    complexity=fs.get("complexity", "medium"),
                    tables_used=json.dumps(fs.get("tables", [])),
                    is_verified=False,
                    is_active=True,
                    source="auto",
                    generated_by="gpt-4"
                )
                db.add(fewshot_record)
                records_created += 1

            db.commit()
            return records_created

        except Exception as e:
            logger.error(f"Failed to store few-shot examples from result: {str(e)}")
            raise

    def _build_connection_string(self, tenant_database: TenantDatabase) -> str:
        """Build SQLAlchemy connection string from TenantDatabase"""
        # Decrypt the password
        password = decrypt_string(tenant_database.password_encrypted)

        db_type = tenant_database.db_type.lower()

        # URL-encode username and password to handle special characters like @
        encoded_username = quote_plus(tenant_database.username)
        encoded_password = quote_plus(password)

        # Log the connection details for debugging (without password)
        logger.info(f"Building connection string: host={tenant_database.host}, port={tenant_database.port}, db={tenant_database.database_name}")

        if db_type == "mssql":
            return (
                f"mssql+pyodbc://{encoded_username}:{encoded_password}@"
                f"{tenant_database.host}:{tenant_database.port}/{tenant_database.database_name}"
                f"?driver=ODBC+Driver+17+for+SQL+Server&TrustServerCertificate=yes"
            )
        elif db_type == "postgresql":
            return (
                f"postgresql://{encoded_username}:{encoded_password}@"
                f"{tenant_database.host}:{tenant_database.port}/{tenant_database.database_name}"
            )
        elif db_type == "mysql":
            return (
                f"mysql+pymysql://{encoded_username}:{encoded_password}@"
                f"{tenant_database.host}:{tenant_database.port}/{tenant_database.database_name}"
            )
        else:
            raise ValueError(f"Unsupported database type: {db_type}")

    def _detect_module_for_table(
        self,
        table_name: str,
        detected_modules: List[str]
    ) -> Optional[str]:
        """
        Try to match a table to a detected module based on naming

        Returns the first matching module or None
        """
        table_lower = table_name.lower()

        for module in detected_modules:
            module_lower = module.lower()

            # Check for common patterns
            module_words = module_lower.replace("-", " ").replace("_", " ").split()

            for word in module_words:
                if len(word) > 2 and word in table_lower:
                    return module

        return None

    def get_onboarding_status(
        self,
        db: Session,
        tenant_db_id: uuid.UUID
    ) -> Dict[str, Any]:
        """
        Get onboarding status for a tenant database

        Returns:
            {
                "is_onboarded": True/False,
                "schema_count": 50,
                "fewshot_count": 50,
                "ready_to_chat": True/False
            }
        """
        schema_count = db.query(SchemaCache).filter(
            SchemaCache.tenant_db_id == tenant_db_id
        ).count()

        fewshot_count = db.query(FewShotExample).filter(
            FewShotExample.tenant_db_id == tenant_db_id,
            FewShotExample.is_active == True
        ).count()

        return {
            "is_onboarded": schema_count > 0,
            "schema_count": schema_count,
            "fewshot_count": fewshot_count,
            "ready_to_chat": schema_count > 0 and fewshot_count > 0
        }

    def get_tenant_schema(
        self,
        db: Session,
        tenant_db_id: uuid.UUID
    ) -> List[SchemaCache]:
        """Get all schema cache records for a tenant database"""
        return db.query(SchemaCache).filter(
            SchemaCache.tenant_db_id == tenant_db_id
        ).all()

    def get_tenant_fewshots(
        self,
        db: Session,
        tenant_db_id: uuid.UUID,
        active_only: bool = True,
        module: Optional[str] = None
    ) -> List[FewShotExample]:
        """Get few-shot examples for a tenant database"""
        query = db.query(FewShotExample).filter(
            FewShotExample.tenant_db_id == tenant_db_id
        )

        if active_only:
            query = query.filter(FewShotExample.is_active == True)

        if module:
            query = query.filter(FewShotExample.module == module)

        return query.all()


# Singleton instance
tenant_onboarding_service = TenantOnboardingService()
