"""
Reindex Database Schemas with Google Embeddings
Script to extract, enrich, and re-index database schemas into ChromaDB using Google Embeddings
"""

import sys
import argparse
from loguru import logger
from datetime import datetime

from app.config import settings
from app.rag.schema_extractor import schema_extractor
from app.rag.schema_enricher import schema_enricher
from app.rag.chroma_manager import chroma_manager

def reindex_schemas_google(limit: int = None, rebuild: bool = False):
    """
    Extract all database schemas, enrich them, and update ChromaDB index
    """
    # Force Google provider settings for this script if not set in env
    if settings.embedding_provider != "google":
        logger.warning("Forcing embedding_provider='google' for this script")
        settings.embedding_provider = "google"
        
    start_time = datetime.now()
    logger.info("=" * 80)
    logger.info("DATABASE SCHEMA RE-INDEXING (GOOGLE EMBEDDINGS)")
    logger.info("=" * 80)

    try:
        # Initialize ChromaDB
        chroma_manager.initialize()
        
        if rebuild:
            logger.warning("Rebuilding index from scratch (deleting existing)")
            chroma_manager.delete_all()

        # Step 1: Extract all table metadata
        logger.info("\n[1/4] Extracting database schemas...")
        tables_metadata = schema_extractor.extract_all_schemas(limit=limit)

        if not tables_metadata:
            logger.error("No tables found to index!")
            return

        logger.info(f"✓ Extracted metadata for {len(tables_metadata)} tables")

        # Step 2: Enrich schemas with AI-generated descriptions
        logger.info("\n[2/4] Enriching schemas with AI-generated descriptions...")
        enriched_tables = schema_enricher.enrich_all_tables(tables_metadata)

        logger.info(f"✓ Generated enriched descriptions for {len(enriched_tables)} tables")

        # Step 3: Prepare documents for ChromaDB
        logger.info("\n[3/4] Preparing documents for vector store...")

        documents = []
        metadatas = []
        ids = []

        for enriched in enriched_tables:
            # Document is the enriched description
            documents.append(enriched["enriched_description"])

            # Metadata includes table info
            metadatas.append({
                "type": "schema",
                "table_name": enriched["table_name"],
                "full_name": enriched["full_name"],
                "num_columns": len(enriched["metadata"]["columns"])
            })

            # ID is the full table name
            ids.append(f"schema_{enriched['full_name']}")

        logger.info(f"✓ Prepared {len(documents)} documents")

        # Step 4: Update ChromaDB index
        logger.info("\n[4/4] Updating ChromaDB vector store...")
        
        chroma_manager.add_schema_embeddings(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )

        # Get final stats
        stats = chroma_manager.get_collection_stats()
        logger.info(f"✓ ChromaDB index now contains {stats['count']} embeddings")

        # Summary
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info("\n" + "=" * 80)
        logger.info("RE-INDEXING COMPLETE")
        logger.info(f"  Tables processed: {len(enriched_tables)}")
        logger.info(f"  Total embeddings: {stats['count']}")
        logger.info(f"  Time elapsed: {elapsed:.2f}s")
        logger.info("=" * 80)

        return {
            "success": True,
            "tables_processed": len(enriched_tables),
            "total_embeddings": stats['count'],
            "elapsed_seconds": elapsed
        }

    except Exception as e:
        logger.error(f"✗ Re-indexing failed: {str(e)}")
        raise

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reindex database schemas into ChromaDB with Google Embeddings")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of tables")
    parser.add_argument("--rebuild", action="store_true", help="Rebuild index from scratch")
    
    args = parser.parse_args()
    
    result = reindex_schemas_google(limit=args.limit, rebuild=args.rebuild)
    
    if result and result["success"]:
        print(f"\n✓ Successfully reindexed {result['tables_processed']} tables")
        sys.exit(0)
    else:
        print("\n✗ Reindexing failed")
        sys.exit(1)
