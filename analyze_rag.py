"""
Deep RAG Analysis Script
Analyzes what's actually happening in the RAG retrieval process
"""

from app.database.connection import init_database
from app.rag.faiss_manager import faiss_manager
from app.agents.sql_agent import RAGSQLAgent

init_database()
faiss_manager.initialize()

# Get FAISS stats
stats = faiss_manager.get_collection_stats()
print("=" * 80)
print("FAISS INDEX STATUS")
print("=" * 80)
print(f"Total embeddings: {stats['count']}")
print(f"\nSample table IDs in index:")
for sample_id in stats['sample_ids'][:5]:
    print(f"  - {sample_id}")

print("\n" + "=" * 80)
print("RAG RETRIEVAL TEST FOR 'IN PUNCHES' QUERY")
print("=" * 80)

# Test query
query = "top 5 employees as highest number of in punches"
print(f"\nUser Query: {query}")

# Step 1: See what FAISS retrieves
print("\n[STEP 1] FAISS Semantic Search Results:")
print("-" * 80)
schema_results = faiss_manager.query_schemas(query, n_results=10)

for i, (doc, meta, dist) in enumerate(zip(
    schema_results['documents'], 
    schema_results['metadatas'],
    schema_results['distances']
), 1):
    print(f"\n{i}. Table: {meta.get('table_name', 'Unknown')}")
    print(f"   Distance: {dist:.4f} (lower = more relevant)")
    print(f"   Schema Preview (first 200 chars):")
    print(f"   {doc[:200]}...")

# Step 2: Check if Attendance/MachinePunch tables are in index
print("\n\n[STEP 2] Checking for Attendance-Related Tables:")
print("-" * 80)
attendance_keywords = ['attendance', 'punch', 'machinepunch', 'biometric', 'intime', 'outtime']

# Search for each keyword
for keyword in attendance_keywords:
    results = faiss_manager.query_schemas(keyword, n_results=3)
    if results['documents']:
        print(f"\n'{keyword}' search results:")
        for meta in results['metadatas']:
            print(f"  - {meta.get('table_name', 'Unknown')}")

# Step 3: Try to retrieve a specific table's enriched description
print("\n\n[STEP 3] Checking Specific Table Descriptions:")
print("-" * 80)

# Try to query for Attendance table directly
for table_name in ['Attendance', 'MachinePunch', 'AttendanceRegister']:
    results = faiss_manager.query_schemas(f"table {table_name}", n_results=1)
    if results['documents']:
        print(f"\n{table_name} table enriched description:")
        print(results['documents'][0][:500])
        print("...")

print("\n" + "=" * 80)
print("ANALYSIS COMPLETE")
print("=" * 80)
