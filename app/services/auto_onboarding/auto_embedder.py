"""
Auto Embedder
Creates ChromaDB embeddings for tenant's schema and few-shots
Supports multi-tenant isolation with tenant-specific collections
"""

import os
from typing import Dict, List, Any, Optional
import chromadb
from chromadb.config import Settings
import google.generativeai as genai
from chromadb import Documents, EmbeddingFunction, Embeddings
from loguru import logger

from app.config import settings


class GoogleEmbeddingFunction(EmbeddingFunction):
    """Custom embedding function for Google Generative AI"""

    def __init__(self, api_key: str, model_name: str, task_type: str = "retrieval_document"):
        genai.configure(api_key=api_key)
        self.model_name = model_name
        self.task_type = task_type

    def __call__(self, input: Documents) -> Embeddings:
        embeddings = []
        for text in input:
            try:
                result = genai.embed_content(
                    model=self.model_name,
                    content=text,
                    task_type=self.task_type
                )
                embeddings.append(result['embedding'])
            except Exception as e:
                logger.error(f"Embedding failed: {e}")
                raise
        return embeddings


class AutoEmbedder:
    """
    Creates ChromaDB embeddings for tenant databases

    Creates two collections per tenant:
    1. {tenant_id}_schema - Table/view descriptions for context
    2. {tenant_id}_fewshots - Q&A pairs for few-shot learning
    """

    def __init__(self, persist_directory: Optional[str] = None):
        """
        Initialize ChromaDB client

        Args:
            persist_directory: Directory for ChromaDB storage
        """
        self.persist_dir = persist_directory or settings.chroma_persist_dir
        os.makedirs(self.persist_dir, exist_ok=True)

        self.client = chromadb.PersistentClient(
            path=self.persist_dir,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )

        # Initialize embedding function
        self.embedding_function = GoogleEmbeddingFunction(
            api_key=settings.gemini_api_key,
            model_name=settings.google_embedding_model,
            task_type="retrieval_document"
        )

        logger.info(f"AutoEmbedder initialized with persist_dir: {self.persist_dir}")

    async def create_tenant_embeddings(
        self,
        tenant_id: str,
        schema: Dict[str, Any],
        analysis: Dict[str, Any],
        few_shots: List[Dict[str, str]]
    ) -> Dict[str, str]:
        """
        Create all embeddings for a tenant - FULLY AUTOMATIC

        Args:
            tenant_id: Unique identifier for tenant
            schema: Full database schema
            analysis: LLM analysis results
            few_shots: Generated Q&A pairs

        Returns:
            {
                "schema_collection": "tenant_123_schema",
                "fewshot_collection": "tenant_123_fewshots",
                "schema_count": 50,
                "fewshot_count": 50
            }
        """
        logger.info(f"Creating embeddings for tenant: {tenant_id}")

        result = {
            "schema_collection": "",
            "fewshot_collection": "",
            "schema_count": 0,
            "fewshot_count": 0
        }

        # Create schema collection
        schema_collection_name = f"{tenant_id}_schema"
        result["schema_collection"] = schema_collection_name
        result["schema_count"] = await self._create_schema_embeddings(
            collection_name=schema_collection_name,
            schema=schema,
            analysis=analysis,
            tenant_id=tenant_id
        )

        # Create few-shot collection
        fewshot_collection_name = f"{tenant_id}_fewshots"
        result["fewshot_collection"] = fewshot_collection_name
        result["fewshot_count"] = await self._create_fewshot_embeddings(
            collection_name=fewshot_collection_name,
            few_shots=few_shots,
            tenant_id=tenant_id
        )

        logger.info(f"Embeddings created: {result}")
        return result

    async def _create_schema_embeddings(
        self,
        collection_name: str,
        schema: Dict[str, Any],
        analysis: Dict[str, Any],
        tenant_id: str
    ) -> int:
        """Create embeddings for schema information"""

        # Delete existing collection if exists
        try:
            self.client.delete_collection(collection_name)
            logger.info(f"Deleted existing collection: {collection_name}")
        except Exception:
            pass  # Collection doesn't exist

        # Create new collection
        collection = self.client.create_collection(
            name=collection_name,
            embedding_function=self.embedding_function,
            metadata={
                "tenant_id": tenant_id,
                "type": "schema",
                "organization_type": analysis.get("organization_type", "Unknown")
            }
        )

        documents = []
        metadatas = []
        ids = []

        # Add organization context
        org_desc = f"""Organization Type: {analysis.get('organization_type', 'Unknown')}
Description: {analysis.get('organization_description', '')}
Modules: {', '.join(analysis.get('detected_modules', []))}
Key Entities: {', '.join(analysis.get('key_entities', []))}"""

        documents.append(org_desc)
        metadatas.append({
            "type": "organization_context",
            "tenant_id": tenant_id
        })
        ids.append(f"{tenant_id}_org_context")

        # Add table descriptions
        table_descriptions = analysis.get("table_descriptions", {})
        for table_name, table_info in schema.get("tables", {}).items():
            # Build rich description
            columns = table_info.get("columns", [])
            col_names = [c["name"] for c in columns[:20]]
            pk = table_info.get("primary_key", [])
            fks = table_info.get("foreign_keys", [])

            description = table_descriptions.get(table_name, f"Table storing {table_name} data")

            doc = f"""Table: {table_name}
Description: {description}
Columns: {', '.join(col_names)}
Primary Key: {', '.join(pk) if pk else 'None'}
Row Count: {table_info.get('row_count', 'Unknown')}"""

            if fks:
                related = [f"{fk['referenced_table']}" for fk in fks[:5]]
                doc += f"\nRelated Tables: {', '.join(related)}"

            documents.append(doc)
            metadatas.append({
                "type": "table_schema",
                "table_name": table_name,
                "tenant_id": tenant_id,
                "has_data": table_info.get("row_count", 0) > 0
            })
            ids.append(f"{tenant_id}_table_{table_name}")

        # Add view descriptions
        view_descriptions = analysis.get("view_descriptions", {})
        for view_name, view_info in schema.get("views", {}).items():
            columns = view_info.get("columns", [])
            col_names = [c["name"] for c in columns[:20]]
            base_tables = view_info.get("base_tables", [])

            description = view_descriptions.get(view_name, f"View combining data")

            doc = f"""View: {view_name}
Description: {description}
Columns: {', '.join(col_names)}
Base Tables: {', '.join(base_tables) if base_tables else 'Unknown'}"""

            documents.append(doc)
            metadatas.append({
                "type": "view_schema",
                "view_name": view_name,
                "tenant_id": tenant_id
            })
            ids.append(f"{tenant_id}_view_{view_name}")

        # Add domain vocabulary
        vocabulary = analysis.get("domain_vocabulary", {})
        if vocabulary:
            vocab_doc = "Domain Vocabulary:\n" + "\n".join([
                f"- {term}: {meaning}" for term, meaning in vocabulary.items()
            ])
            documents.append(vocab_doc)
            metadatas.append({
                "type": "domain_vocabulary",
                "tenant_id": tenant_id
            })
            ids.append(f"{tenant_id}_vocabulary")

        # Batch add to collection
        if documents:
            # Add in batches to avoid token limits
            batch_size = 50
            for i in range(0, len(documents), batch_size):
                batch_docs = documents[i:i+batch_size]
                batch_meta = metadatas[i:i+batch_size]
                batch_ids = ids[i:i+batch_size]

                try:
                    collection.add(
                        documents=batch_docs,
                        metadatas=batch_meta,
                        ids=batch_ids
                    )
                except Exception as e:
                    logger.warning(f"Failed to add batch {i}: {e}")

        logger.info(f"Created {len(documents)} schema embeddings in {collection_name}")
        return len(documents)

    async def _create_fewshot_embeddings(
        self,
        collection_name: str,
        few_shots: List[Dict[str, str]],
        tenant_id: str
    ) -> int:
        """Create embeddings for few-shot examples"""

        # Delete existing collection if exists
        try:
            self.client.delete_collection(collection_name)
        except Exception:
            pass

        # Create new collection
        collection = self.client.create_collection(
            name=collection_name,
            embedding_function=self.embedding_function,
            metadata={
                "tenant_id": tenant_id,
                "type": "fewshots"
            }
        )

        documents = []
        metadatas = []
        ids = []

        for i, fs in enumerate(few_shots):
            question = fs.get("question", "")
            sql = fs.get("sql", "")
            module = fs.get("module", "general")
            complexity = fs.get("complexity", "medium")
            tables_used = fs.get("tables_used", [])

            if not question or not sql:
                continue

            # Embed the question (what we search by)
            documents.append(question)
            metadatas.append({
                "type": "fewshot",
                "sql": sql,
                "module": module,
                "complexity": complexity,
                "tables_used": ",".join(tables_used) if tables_used else "",
                "tenant_id": tenant_id
            })
            ids.append(f"{tenant_id}_fs_{i}")

        # Batch add
        if documents:
            batch_size = 50
            for i in range(0, len(documents), batch_size):
                batch_docs = documents[i:i+batch_size]
                batch_meta = metadatas[i:i+batch_size]
                batch_ids = ids[i:i+batch_size]

                try:
                    collection.add(
                        documents=batch_docs,
                        metadatas=batch_meta,
                        ids=batch_ids
                    )
                except Exception as e:
                    logger.warning(f"Failed to add few-shot batch {i}: {e}")

        logger.info(f"Created {len(documents)} few-shot embeddings in {collection_name}")
        return len(documents)

    def query_schema(
        self,
        tenant_id: str,
        query: str,
        n_results: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Query schema collection for relevant context

        Args:
            tenant_id: Tenant identifier
            query: Natural language query
            n_results: Number of results

        Returns:
            List of relevant schema documents with metadata
        """
        collection_name = f"{tenant_id}_schema"

        try:
            collection = self.client.get_collection(
                name=collection_name,
                embedding_function=self.embedding_function
            )

            results = collection.query(
                query_texts=[query],
                n_results=n_results
            )

            return [
                {
                    "document": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i],
                    "distance": results["distances"][0][i] if results.get("distances") else None
                }
                for i in range(len(results["documents"][0]))
            ]

        except Exception as e:
            logger.error(f"Schema query failed: {e}")
            return []

    def query_fewshots(
        self,
        tenant_id: str,
        query: str,
        n_results: int = 5,
        module_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Query few-shot collection for similar examples

        Args:
            tenant_id: Tenant identifier
            query: Natural language query
            n_results: Number of results
            module_filter: Optional module to filter by

        Returns:
            List of similar Q&A pairs
        """
        collection_name = f"{tenant_id}_fewshots"

        try:
            collection = self.client.get_collection(
                name=collection_name,
                embedding_function=self.embedding_function
            )

            where_filter = None
            if module_filter:
                where_filter = {"module": module_filter}

            results = collection.query(
                query_texts=[query],
                n_results=n_results,
                where=where_filter
            )

            return [
                {
                    "question": results["documents"][0][i],
                    "sql": results["metadatas"][0][i].get("sql", ""),
                    "module": results["metadatas"][0][i].get("module", ""),
                    "complexity": results["metadatas"][0][i].get("complexity", ""),
                    "distance": results["distances"][0][i] if results.get("distances") else None
                }
                for i in range(len(results["documents"][0]))
            ]

        except Exception as e:
            logger.error(f"Few-shot query failed: {e}")
            return []

    def delete_tenant_collections(self, tenant_id: str):
        """Delete all collections for a tenant"""
        try:
            self.client.delete_collection(f"{tenant_id}_schema")
            logger.info(f"Deleted schema collection for {tenant_id}")
        except Exception:
            pass

        try:
            self.client.delete_collection(f"{tenant_id}_fewshots")
            logger.info(f"Deleted few-shot collection for {tenant_id}")
        except Exception:
            pass

    def get_collection_stats(self, tenant_id: str) -> Dict[str, Any]:
        """Get statistics for tenant's collections"""
        stats = {
            "schema_count": 0,
            "fewshot_count": 0
        }

        try:
            schema_col = self.client.get_collection(f"{tenant_id}_schema")
            stats["schema_count"] = schema_col.count()
        except Exception:
            pass

        try:
            fewshot_col = self.client.get_collection(f"{tenant_id}_fewshots")
            stats["fewshot_count"] = fewshot_col.count()
        except Exception:
            pass

        return stats
