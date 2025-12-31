"""
ChromaDB Manager for RAG System
Handles vector store operations for database schema embeddings
"""

from typing import List, Dict, Any, Optional
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
from loguru import logger
import os
import google.generativeai as genai
from chromadb import Documents, EmbeddingFunction, Embeddings

from app.config import settings


class ChromaDBManager:
    """
    Manages ChromaDB vector store for schema embeddings
    Manages ChromaDB vector store for schema embeddings
    Stores table schemas, column information, and example queries
    """

    class GoogleEmbeddingFunction(EmbeddingFunction):
        """
        Custom embedding function for Google Generative AI
        """
        def __init__(self, api_key: str, model_name: str, task_type: str = "retrieval_document"):
            genai.configure(api_key=api_key)
            self.model_name = model_name
            self.task_type = task_type

        def __call__(self, input: Documents) -> Embeddings:
            # Batch embed with Google's API
            embeddings = []
            # Google API handles batching, but we might want to chunk if too large
            # For now, simple iteration or direct list pass if supported
            # The genai.embed_content supports a single content or list? 
            # It seems it supports single content mostly in current SDK versions or list.
            # Let's iterate to be safe and handle errors per item if needed, 
            # or use batch method if available. 
            # Actually, let's use a loop for safety and error handling.
            
            for text in input:
                try:
                    result = genai.embed_content(
                        model=self.model_name,
                        content=text,
                        task_type=self.task_type
                    )
                    embeddings.append(result['embedding'])
                except Exception as e:
                    logger.error(f"Google embedding failed for text: {text[:50]}... Error: {e}")
                    # Return zero vector or raise? Raising is better to catch issues.
                    raise e
            return embeddings

    def __init__(self):
        """Initialize ChromaDB client and collection"""
        self.client: Optional[chromadb.Client] = None
        self.collection: Optional[chromadb.Collection] = None
        self.embedding_function = None
        self._initialized = False

    def initialize(self):
        """
        Initialize ChromaDB client and create/load collection

        Creates persistent client with embeddings using sentence-transformers
        """
        if self._initialized:
            logger.warning("ChromaDB already initialized")
            return

        try:
            logger.info("Initializing ChromaDB...")

            # Ensure persist directory exists
            os.makedirs(settings.chroma_persist_dir, exist_ok=True)

            # Initialize embedding function
            if settings.embedding_provider == "google":
                logger.info(f"Using Google Embeddings: {settings.google_embedding_model}")
                self.embedding_function = self.GoogleEmbeddingFunction(
                    api_key=settings.gemini_api_key,
                    model_name=settings.google_embedding_model,
                    task_type=settings.google_embedding_task_type
                )
            else:
                logger.info(f"Using Sentence Transformers: {settings.embedding_model}")
                self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
                    model_name=settings.embedding_model,
                    device=settings.embedding_device
                )

            # Create persistent ChromaDB client
            self.client = chromadb.PersistentClient(
                path=settings.chroma_persist_dir,
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )

            # Get or create collection
            self.collection = self.client.get_or_create_collection(
                name=settings.chroma_collection_name,
                embedding_function=self.embedding_function,
                metadata={"description": "Database schema embeddings for RAG"}
            )

            self._initialized = True
            logger.info(f"[OK] ChromaDB initialized with {self.collection.count()} embeddings")

        except Exception as e:
            logger.error(f"[ERROR] ChromaDB initialization failed: {str(e)}")
            raise

    def add_schema_embeddings(
        self,
        documents: List[str],
        metadatas: List[Dict[str, Any]],
        ids: List[str]
    ):
        """
        Add schema documents to vector store

        Args:
            documents: List of schema text descriptions
            metadatas: List of metadata dicts (table_name, column_names, etc.)
            ids: List of unique IDs for each document

        Example:
            documents = ["Table: EmployeeMaster. Columns: Ecode, EmpName, ..."]
            metadatas = [{"table": "EmployeeMaster", "type": "schema"}]
            ids = ["schema_EmployeeMaster"]
        """
        if not self._initialized:
            raise RuntimeError("ChromaDB not initialized")

        try:
            self.collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            logger.info(f"[OK] Added {len(documents)} schema embeddings")

        except Exception as e:
            logger.error(f"[ERROR] Failed to add embeddings: {str(e)}")
            raise

    def query_schemas(
        self,
        query_text: str,
        n_results: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Query vector store for relevant schemas

        Args:
            query_text: Natural language query
            n_results: Number of results to return
            filter_metadata: Optional metadata filter

        Returns:
            Dict with keys: 'documents', 'metadatas', 'distances'

        Example:
            results = manager.query_schemas(
                "Show me employee information",
                n_results=3
            )
        """
        if not self._initialized:
            raise RuntimeError("ChromaDB not initialized")

        try:
            results = self.collection.query(
                query_texts=[query_text],
                n_results=n_results,
                where=filter_metadata
            )

            logger.info(f"[OK] Retrieved {len(results['documents'][0])} relevant schemas")
            return {
                "documents": results["documents"][0],
                "metadatas": results["metadatas"][0],
                "distances": results["distances"][0]
            }

        except Exception as e:
            logger.error(f"[ERROR] Query failed: {str(e)}")
            raise

    def delete_all(self):
        """
        Delete all embeddings from collection
        Useful for re-indexing
        """
        if not self._initialized:
            raise RuntimeError("ChromaDB not initialized")

        try:
            # Get all IDs
            all_items = self.collection.get()
            if all_items["ids"]:
                self.collection.delete(ids=all_items["ids"])
                logger.info(f"[OK] Deleted {len(all_items['ids'])} embeddings")
            else:
                logger.info("No embeddings to delete")

        except Exception as e:
            logger.error(f"[ERROR] Delete failed: {str(e)}")
            raise

    def get_collection_stats(self) -> Dict[str, Any]:
        """
        Get collection statistics

        Returns:
            Dict with count and sample documents
        """
        if not self._initialized:
            raise RuntimeError("ChromaDB not initialized")

        count = self.collection.count()
        sample = self.collection.peek(limit=3)

        return {
            "count": count,
            "sample_ids": sample["ids"],
            "sample_documents": sample["documents"][:3] if sample["documents"] else []
        }

    def close(self):
        """Close ChromaDB client"""
        if self.client:
            # ChromaDB handles persistence automatically
            self._initialized = False
            logger.info("[OK] ChromaDB connection closed")


# Global ChromaDB manager instance
chroma_manager = ChromaDBManager()
