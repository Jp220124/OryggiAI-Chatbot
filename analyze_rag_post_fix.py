"""
Deep RAG Analysis Script - Post Fix
"""

from app.database.connection import init_database
from app.rag.faiss_manager import faiss_manager

init_database()
faiss_manager.initialize()

# Test query
query = "top 5 employees as highest number of in punches"
print(f"\nUser Query: {query}")

# Step 1: See what FAISS retrieves (Top 10)
print("\n[STEP 1] FAISS Semantic Search Results (Top 10):")
print("-" * 80)
schema_results = faiss_manager.query_schemas(query, n_results=10)

for i, (doc, meta, dist) in enumerate(zip(
    schema_results['documents'], 
    schema_results['metadatas'],
    schema_results['distances']
), 1):
    print(f"\n{i}. Table: {meta.get('table_name', 'Unknown')}")
    print(f"   Distance: {dist:.4f}")
    if "KEYWORDS" in doc:
        print("   [HAS KEYWORDS]")
    else:
        print("   [NO KEYWORDS]")
    print(f"   Preview: {doc[:100]}...")

# Step 2: Check AttendanceRegister specifically
print("\n\n[STEP 2] Checking AttendanceRegister Content:")
print("-" * 80)
results = faiss_manager.query_schemas("AttendanceRegister", n_results=1)
if results['documents']:
    print(results['documents'][0])
