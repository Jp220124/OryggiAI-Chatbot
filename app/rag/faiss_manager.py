"""
FAISS Manager for RAG System
Handles vector store operations for database schema embeddings
"""

from typing import List, Dict, Any, Optional
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
try:
    from langchain.schema import Document
except ImportError:
    from langchain_core.documents import Document
from loguru import logger
import os
import pickle

from app.config import settings


class FAISSManager:
    """
    Manages FAISS vector store for schema embeddings
    Stores table schemas, column information, and example queries
    """

    def __init__(self):
        """Initialize FAISS manager"""
        self.vectorstore: Optional[FAISS] = None
        self.embeddings: Optional[HuggingFaceEmbeddings] = None
        self._initialized = False
        self.index_path = settings.faiss_index_path
        self.metadata_path = f"{settings.faiss_index_path}/metadata.pkl"

    def initialize(self):
        """
        Initialize FAISS vector store and embeddings

        Creates or loads existing FAISS index with sentence-transformers embeddings
        """
        if self._initialized:
            logger.warning("FAISS already initialized")
            return

        try:
            logger.info("Initializing FAISS...")

            # Ensure index directory exists
            os.makedirs(self.index_path, exist_ok=True)

            # Initialize embedding function
            self.embeddings = HuggingFaceEmbeddings(
                model_name=settings.embedding_model,
                model_kwargs={"device": settings.embedding_device}
            )

            # Try to load existing index
            index_file = f"{self.index_path}/index.faiss"
            if os.path.exists(index_file):
                logger.info("Loading existing FAISS index...")
                self.vectorstore = FAISS.load_local(
                    self.index_path,
                    self.embeddings,
                    allow_dangerous_deserialization=True
                )
                count = len(self.vectorstore.docstore._dict)
                logger.info(f"[OK] FAISS loaded with {count} embeddings")
            else:
                logger.info("No existing index found - will create on first add")
                # Will be created when first documents are added

            self._initialized = True

        except Exception as e:
            logger.error(f"[ERROR] FAISS initialization failed: {str(e)}")
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
            raise RuntimeError("FAISS not initialized")

        try:
            # Create Document objects with metadata
            docs = [
                Document(page_content=doc, metadata={**meta, "id": doc_id})
                for doc, meta, doc_id in zip(documents, metadatas, ids)
            ]

            if self.vectorstore is None:
                # Create new index
                logger.info("Creating new FAISS index...")
                self.vectorstore = FAISS.from_documents(docs, self.embeddings)
            else:
                # Add to existing index
                self.vectorstore.add_documents(docs)

            # Save index to disk
            self.vectorstore.save_local(self.index_path)
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
            filter_metadata: Optional metadata filter (limited support in FAISS)

        Returns:
            Dict with keys: 'documents', 'metadatas', 'distances'

        Example:
            results = manager.query_schemas(
                "Show me employee information",
                n_results=3
            )
        """
        if not self._initialized:
            raise RuntimeError("FAISS not initialized")

        if self.vectorstore is None:
            logger.warning("No documents in FAISS index")
            return {
                "documents": [],
                "metadatas": [],
                "distances": []
            }

        try:
            # Perform similarity search with scores
            results = self.vectorstore.similarity_search_with_score(
                query_text,
                k=n_results
            )

            documents = []
            metadatas = []
            distances = []

            for doc, score in results:
                # Apply metadata filter if provided
                if filter_metadata:
                    matches = all(
                        doc.metadata.get(k) == v
                        for k, v in filter_metadata.items()
                    )
                    if not matches:
                        continue

                documents.append(doc.page_content)
                metadatas.append(doc.metadata)
                # FAISS returns similarity scores, convert to distance-like metric
                distances.append(float(score))

            logger.info(f"[OK] Retrieved {len(documents)} relevant schemas")
            return {
                "documents": documents,
                "metadatas": metadatas,
                "distances": distances
            }

        except Exception as e:
            logger.error(f"[ERROR] Query failed: {str(e)}")
            raise

    def delete_all(self):
        """
        Delete all embeddings from vector store
        Useful for re-indexing
        """
        if not self._initialized:
            raise RuntimeError("FAISS not initialized")

        try:
            # Delete index files
            index_file = f"{self.index_path}/index.faiss"
            pkl_file = f"{self.index_path}/index.pkl"

            count = 0
            if self.vectorstore:
                count = len(self.vectorstore.docstore._dict)

            # Remove files if they exist
            if os.path.exists(index_file):
                os.remove(index_file)
            if os.path.exists(pkl_file):
                os.remove(pkl_file)

            # Reset vectorstore
            self.vectorstore = None

            logger.info(f"[OK] Deleted {count} embeddings")

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
            raise RuntimeError("FAISS not initialized")

        if self.vectorstore is None:
            return {
                "count": 0,
                "sample_ids": [],
                "sample_documents": []
            }

        count = len(self.vectorstore.docstore._dict)

        # Get sample documents
        sample_docs = list(self.vectorstore.docstore._dict.values())[:3]
        sample_ids = [doc.metadata.get("id", "unknown") for doc in sample_docs]
        sample_documents = [doc.page_content for doc in sample_docs]

        return {
            "count": count,
            "sample_ids": sample_ids,
            "sample_documents": sample_documents
        }

    def close(self):
        """Close FAISS manager"""
        if self.vectorstore:
            # FAISS is already persisted to disk
            self._initialized = False
            logger.info("[OK] FAISS manager closed")


# Global FAISS manager instance
faiss_manager = FAISSManager()
