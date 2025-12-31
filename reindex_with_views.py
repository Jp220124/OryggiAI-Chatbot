"""
Re-index Schema with Priority Database Views
This script re-indexes the schema to include priority views alongside tables
"""
import os
os.environ['DEPLOYMENT_ENV'] = 'development'

from app.rag import chroma_manager
from app.rag.schema_extractor import schema_extractor
from app.rag.schema_enricher import schema_enricher
from loguru import logger

def reindex_with_views():
    """Re-index schema including priority database views"""
    
    logger.info("=" * 80)
    logger.info("RE-INDEXING SCHEMA WITH DATABASE VIEWS")
    logger.info("="  * 80)
    
    # Initialize ChromaDB
    logger.info("\n[1] Initializing ChromaDB...")
    chroma_manager.initialize()
    
    # Clear existing collection
    logger.info("\n[2] Clearing existing schema embeddings...")
    try:
        chroma_manager.delete_collection()
        chroma_manager.initialize()  # Recreate
        logger.info("\u2713 Collection cleared")
    except Exception as e:
        logger.warning(f"Could not clear collection: {e}")
    
    # Extract priority views
    logger.info("\n[3] Extracting priority views...")
    priority_views = schema_extractor.get_priority_views("dbo")
    logger.info(f"\u2713 Found {len(priority_views)} priority views to index")
    
    # Show which views will be indexed
    for view in priority_views:
        logger.info(f"   - {view}")
    
    # Extract view metadata
    logger.info("\n[4] Extracting view metadata...")
    view_metadata = []
    for view_name in priority_views:
        try:
            metadata = schema_extractor.extract_view_metadata(view_name, "dbo")
            view_metadata.append(metadata)
            logger.info(f"\u2713 {view_name}: {len(metadata['columns'])} columns, base tables: {metadata['base_tables']}")
        except Exception as e:
            logger.error(f"\u2717 Failed to extract {view_name}: {e}")
    
    logger.info(f"\n\u2713 Extracted metadata for {len(view_metadata)} views")
    
    # Extract table metadata (limit to important tables not fully covered by views)
    logger.info("\n[5] Extracting table metadata (limited set)...")
    
    # Only extract key tables that provide additional context not in views
    # Note: Many tables are already covered by the views, so we limit this list
    important_tables = [
        # Core masters for reference (views already include these joined)
        'ShiftMaster', 'PolicyMaster', 'HolidayMaster',
        'LeaveMaster', 'LeaveTypeMaster',
        # Machine and device config
        'MachineMaster', 'AuthenticationMaster',
        # Status and classification
        'StatusMaster', 'RoleMaster'
    ]
    
    table_metadata = []
    for table_name in important_tables:
        try:
            metadata = schema_extractor.extract_table_metadata(table_name, "dbo")
            table_metadata.append(metadata)
            logger.info(f"\u2713 {table_name}")
        except Exception as e:
            logger.warning(f"\u2717 {table_name}: {e}")
    
    logger.info(f"\n\u2713 Extracted metadata for {len(table_metadata)} tables")
    
    # Combine all metadata
    all_metadata = view_metadata + table_metadata
    logger.info(f"\n[6] Total metadata items: {len(all_metadata)} ({len(view_metadata)} views + {len(table_metadata)} tables)")
    
    # Enrich and add to ChromaDB
    logger.info("\n[7] Enriching and indexing metadata...")
    enriched_count = 0
    
    for metadata in all_metadata:
        try:
            # Enrich metadata
            enriched = schema_enricher.enrich_metadata(metadata)
            
            # Add to ChromaDB
            chroma_manager.add_table_schema(enriched)
            enriched_count += 1
            
            obj_type = metadata.get('type', 'TABLE')
            obj_name = metadata.get('view_name', metadata.get('table_name', 'Unknown'))
            logger.info(f"\u2713 Indexed {obj_type}: {obj_name}")
            
        except Exception as e:
            logger.error(f"\u2717 Failed to index {metadata.get('full_name')}: {e}")
    
    # Get final stats
    stats = chroma_manager.get_collection_stats()
    
    logger.info("\n" + "=" * 80)
    logger.info("RE-INDEXING COMPLETE")
    logger.info("=" * 80)
    logger.info(f"Views indexed: {len(view_metadata)}")
    logger.info(f"Tables indexed: {len(table_metadata)}")
    logger.info(f"Total embeddings: {stats['count']}")
    logger.info("=" * 80)
    
    return {
        'views_indexed': len(view_metadata),
        'tables_indexed': len(table_metadata),
        'total_embeddings': stats['count'],
        'priority_views': priority_views
    }

if __name__ == "__main__":
    result = reindex_with_views()
    
    print("\n\nSUMMARY:")
    print(f"  Views indexed: {result['views_indexed']}")
    print(f"  Tables indexed: {result['tables_indexed']}")
    print(f"  Total embeddings: {result['total_embeddings']}")
    print(f"\nPriority views indexed:")
    for view in result['priority_views']:
        print(f"  - {view}")
