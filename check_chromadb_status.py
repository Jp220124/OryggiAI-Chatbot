"""
Check ChromaDB Status After Re-indexing
"""
import os
os.environ['DEPLOYMENT_ENV'] = 'development'

from app.rag import chroma_manager

print("Checking ChromaDB status...")
chroma_manager.initialize()

stats = chroma_manager.get_collection_stats()

print(f"\nChromaDB Collection Stats:")
print(f"  Total embeddings: {stats['count']}")
print(f"  Collection name: {stats.get('name', 'N/A')}")

# Try to retrieve some schemas
if stats['count'] > 0:
    print(f"\n\nTesting schema retrieval for critical views...")
    
    critical_views = [
        'AllEmployeeUnion',
        'vw_RawPunchDetail',
        'vw_EmployeeMaster_Vms'
    ]
    
    for view_name in critical_views:
        try:
            results = chroma_manager.get_relevant_schemas(f"get data from {view_name}", k=1)
            if results:
                found = False
                for result in results:
                    if view_name.lower() in result.get('full_name', '').lower():
                        print(f"  ✓ {view_name} - FOUND")
                        found = True
                        break
                if not found:
                    print(f"  ✗ {view_name} - NOT FOUND (but got {len(results)} results)")
            else:
                print(f"  ✗ {view_name} - NO RESULTS")
        except Exception as e:
            print(f"  ✗ {view_name} - ERROR: {e}")
else:
    print("\n⚠ No embeddings found in collection!")

print("\n" + "="*60)
