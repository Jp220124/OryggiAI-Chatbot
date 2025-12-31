"""
Reindex Database Schemas
Script to extract, enrich, and re-index database schemas into FAISS
"""

import sys
from loguru import logger
from datetime import datetime

from app.rag.schema_extractor import schema_extractor
from app.rag.schema_enricher import schema_enricher
from app.rag.faiss_manager import faiss_manager


def reindex_schemas(limit: int = None, rebuild: bool = False):
    """
    Extract all database schemas, enrich them, and update FAISS index

    Args:
        limit: Optional limit on number of tables to process (for testing)
        rebuild: If True, delete existing index and rebuild from scratch
    """
    start_time = datetime.now()
    logger.info("=" * 80)
    logger.info("DATABASE SCHEMA RE-INDEXING")
    logger.info("=" * 80)

    try:
        # Step 1: Extract all table metadata
        logger.info("\n[1/4] Extracting database schemas...")
        tables_metadata = schema_extractor.extract_all_schemas(limit=limit)

        if not tables_metadata:
            logger.error("No tables found to index!")
            return

        logger.info(f"✓ Extracted metadata for {len(tables_metadata)} tables")

        # Step 2: Enrich schemas with semantic descriptions
        logger.info("\n[2/4] Enriching schemas with AI-generated descriptions...")
        enriched_tables = schema_enricher.enrich_all_tables(tables_metadata)

        logger.info(f"✓ Generated enriched descriptions for {len(enriched_tables)} tables")

        # Step 3: Prepare documents for FAISS
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

        # Step 4: Update FAISS index
        logger.info("\n[4/4] Updating FAISS vector store...")

        # Initialize FAISS if not already done
        faiss_manager.initialize()

        if rebuild:
            logger.warning("Rebuilding index from scratch (deleting existing)")
            faiss_manager.delete_all()

        # Add enriched schemas to FAISS
        faiss_manager.add_schema_embeddings(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )

        # Get final stats
        stats = faiss_manager.get_collection_stats()
        logger.info(f"✓ FAISS index now contains {stats['count']} embeddings")

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
    """
    Run from command line:
    python reindex_schemas.py             # Index all tables
    python reindex_schemas.py --limit 10  # Index first 10 tables (testing)
    python reindex_schemas.py --rebuild   # Rebuild index from scratch
    """
    import argparse

    parser = argparse.ArgumentParser(description="Reindex database schemas into FAISS")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of tables to process (for testing)"
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Rebuild index from scratch (delete existing)"
    )

    args = parser.parse_args()

    # Run reindexing
    result = reindex_schemas(limit=args.limit, rebuild=args.rebuild)

    if result["success"]:
        print(f"\n✓ Successfully reindexed {result['tables_processed']} tables")
        sys.exit(0)
    else:
        print("\n✗ Reindexing failed")
        sys.exit(1)
