"""
Auto-Onboarding Service
Fully automatic database onboarding - zero configuration required

This service automatically:
1. Extracts complete database schema
2. Detects organization NAME and TYPE from actual DATA (not just schema)
3. Uses LLM to understand business modules
4. Generates domain-specific few-shot Q&A examples
5. Creates ChromaDB embeddings for RAG

KEY FEATURE: Data-driven context detection
- Same OryggiDB schema used by Universities, Coal Mines, Metros
- System analyzes DATA to identify: "MUJ University" vs "Vedanta Mine" vs "Delhi Metro"

User just connects database -> System understands EVERYTHING
"""

from .schema_extractor import AutoSchemaExtractor
from .llm_analyzer import LLMSchemaAnalyzer
from .fewshot_generator import AutoFewShotGenerator
from .auto_embedder import AutoEmbedder
from .orchestrator import OnboardingOrchestrator
from .data_context_detector import DataContextDetector  # NEW: Data-driven detection

__all__ = [
    "AutoSchemaExtractor",
    "LLMSchemaAnalyzer",
    "AutoFewShotGenerator",
    "AutoEmbedder",
    "OnboardingOrchestrator",
    "DataContextDetector"
]
