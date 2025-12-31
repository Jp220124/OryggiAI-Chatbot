"""
Few-Shot Example Manager
Retrieves relevant SQL query examples to enhance prompt engineering
"""

from typing import List, Dict, Any, Optional
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
try:
    from langchain.schema import Document
except ImportError:
    from langchain_core.documents import Document
from loguru import logger
import json
import os

from app.config import settings


class FewShotManager:
    """
    Manages few-shot examples for SQL query generation
    Uses FAISS to retrieve relevant examples based on question similarity
    """

    def __init__(self):
        """Initialize Few-Shot Manager"""
        self.examples: List[Dict[str, Any]] = []
        self.vectorstore: Optional[FAISS] = None
        self.embeddings: Optional[HuggingFaceEmbeddings] = None
        self._initialized = False
        self.examples_path = "./data/few_shot_examples.json"
        self.index_path = f"{settings.faiss_index_path}/few_shot"

    def initialize(self):
        """
        Initialize few-shot manager
        Loads examples and creates/loads FAISS index
        """
        if self._initialized:
            logger.warning("FewShotManager already initialized")
            return

        try:
            logger.info("Initializing FewShotManager...")

            # Load examples from JSON
            self.examples = self._load_examples()
            logger.info(f"Loaded {len(self.examples)} few-shot examples")

            # Initialize embedding function (reuse same as schema embeddings)
            self.embeddings = HuggingFaceEmbeddings(
                model_name=settings.embedding_model,
                model_kwargs={"device": settings.embedding_device}
            )

            # Try to load existing index
            os.makedirs(self.index_path, exist_ok=True)
            index_file = f"{self.index_path}/index.faiss"

            if os.path.exists(index_file):
                logger.info("Loading existing few-shot FAISS index...")
                self.vectorstore = FAISS.load_local(
                    self.index_path,
                    self.embeddings,
                    allow_dangerous_deserialization=True
                )
                logger.info(f"[OK] Loaded few-shot index with {len(self.vectorstore.docstore._dict)} examples")
            else:
                # Create new index from examples
                logger.info("Creating new few-shot FAISS index...")
                self._create_index()
                logger.info(f"[OK] Created few-shot index with {len(self.examples)} examples")

            self._initialized = True

        except Exception as e:
            logger.error(f"[ERROR] FewShotManager initialization failed: {str(e)}")
            raise

    def _load_examples(self) -> List[Dict[str, Any]]:
        """
        Load examples from JSON file

        Returns:
            List of example dictionaries
        """
        try:
            with open(self.examples_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get("examples", [])
        except FileNotFoundError:
            logger.warning(f"Few-shot examples file not found: {self.examples_path}")
            return []
        except Exception as e:
            logger.error(f"[ERROR] Failed to load examples: {str(e)}")
            return []

    def _create_index(self):
        """
        Create FAISS index from examples
        Embeds all example questions for similarity search
        """
        if not self.examples:
            logger.warning("No examples to index")
            return

        # Create documents from examples (embed the question + explanation)
        documents = []
        for example in self.examples:
            # Combine question and explanation for better retrieval
            doc_text = f"{example['question']}\n{example['explanation']}"

            doc = Document(
                page_content=doc_text,
                metadata={
                    "id": example["id"],
                    "category": example["category"],
                    "question": example["question"],
                    "sql": example["sql"],
                    "explanation": example["explanation"],
                    "tables_used": example["tables_used"],
                    "concepts": example.get("concepts", [])
                }
            )
            documents.append(doc)

        # Create FAISS index
        self.vectorstore = FAISS.from_documents(documents, self.embeddings)

        # Save index to disk
        self.vectorstore.save_local(self.index_path)
        logger.info(f"[OK] Saved few-shot index to {self.index_path}")

    def get_relevant_examples(
        self,
        question: str,
        n_results: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Retrieve most relevant few-shot examples for a question

        Args:
            question: User's natural language question
            n_results: Number of examples to retrieve (default: 3)

        Returns:
            List of relevant example dictionaries

        Example:
            examples = manager.get_relevant_examples(
                "How many employees in IT?",
                n_results=3
            )
        """
        if not self._initialized:
            logger.warning("FewShotManager not initialized")
            return []

        if not self.vectorstore:
            logger.warning("No vectorstore available")
            return []

        try:
            # Perform similarity search
            results = self.vectorstore.similarity_search_with_score(
                question,
                k=n_results
            )

            relevant_examples = []
            for doc, score in results:
                example = {
                    "id": doc.metadata.get("id"),
                    "category": doc.metadata.get("category"),
                    "question": doc.metadata.get("question"),
                    "sql": doc.metadata.get("sql"),
                    "explanation": doc.metadata.get("explanation"),
                    "tables_used": doc.metadata.get("tables_used", []),
                    "similarity_score": float(score)
                }
                relevant_examples.append(example)

            logger.info(f"[OK] Retrieved {len(relevant_examples)} relevant examples")
            return relevant_examples

        except Exception as e:
            logger.error(f"[ERROR] Failed to retrieve examples: {str(e)}")
            return []

    def format_examples_for_prompt(self, examples: List[Dict[str, Any]]) -> str:
        """
        Format few-shot examples for inclusion in prompt

        Args:
            examples: List of example dictionaries

        Returns:
            Formatted string for prompt

        Example output:
            EXAMPLE 1:
            Question: How many employees in IT?
            SQL: SELECT COUNT(*) FROM EmployeeMaster WHERE DeptCode = 'IT'
            Explanation: Count with WHERE clause

            EXAMPLE 2:
            ...
        """
        if not examples:
            return ""

        formatted = "RELEVANT EXAMPLES:\n\n"

        for i, example in enumerate(examples, 1):
            formatted += f"EXAMPLE {i}:\n"
            formatted += f"Question: {example['question']}\n"
            formatted += f"SQL: {example['sql']}\n"
            formatted += f"Explanation: {example['explanation']}\n"

            # Add tables used
            if example.get('tables_used'):
                formatted += f"Tables: {', '.join(example['tables_used'])}\n"

            formatted += "\n"

        formatted += "Now, generate a similar SQL query for the user's question below.\n\n"

        return formatted

    def get_examples_by_category(self, category: str) -> List[Dict[str, Any]]:
        """
        Get all examples in a specific category

        Args:
            category: Category name (e.g., "simple_count", "join", etc.)

        Returns:
            List of examples in that category
        """
        return [ex for ex in self.examples if ex.get("category") == category]

    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about few-shot examples

        Returns:
            Dict with statistics
        """
        if not self.examples:
            return {
                "total_examples": 0,
                "categories": []
            }

        categories = {}
        for example in self.examples:
            cat = example.get("category", "unknown")
            categories[cat] = categories.get(cat, 0) + 1

        return {
            "total_examples": len(self.examples),
            "categories": categories,
            "initialized": self._initialized
        }

    def reload_examples(self):
        """
        Reload examples from JSON and recreate index
        Use this when examples file is updated
        """
        logger.info("Reloading few-shot examples...")

        # Load fresh examples
        self.examples = self._load_examples()

        # Recreate index
        if self.embeddings:
            self._create_index()
            logger.info(f"[OK] Reloaded {len(self.examples)} examples")
        else:
            logger.warning("Embeddings not initialized, call initialize() first")


# Global few-shot manager instance
few_shot_manager = FewShotManager()
