"""
Test enriched schema with sample queries
"""

from app.rag.faiss_manager import faiss_manager
from app.agents.sql_agent import RAGSQLAgent

# Initialize
faiss_manager.initialize()
agent = RAGSQLAgent()

# Test query that previously failed
test_question = "Generate report showing Employees In and out counts"

print("=" * 80)
print(f"TEST QUERY: {test_question}")
print("=" * 80)

# Check what schema context is retrieved
print("\n[1] Retrieving schema context...")
schema_context = faiss_manager.query_schemas(test_question, n_results=5)

print(f"\nRetrieved {len(schema_context['documents'])} relevant schemas:")
for i, (doc, meta) in enumerate(zip(schema_context['documents'], schema_context['metadatas']), 1):
    print(f"\n--- Schema {i}: {meta.get('table_name', 'Unknown')} ---")
    print(doc[:300] + "..." if len(doc) > 300 else doc)

# Generate SQL
print("\n\n[2] Generating SQL query...")
try:
    result = agent.generate_sql(test_question)
    print(f"\nSUCCESS - Generated SQL:")
    print(result['sql_query'])
    print(f"\nExplanation: {result['explanation']}")
    print(f"Tables used: {result.get('tables_referenced', [])}")
except Exception as e:
    print(f"\nFAILED: {str(e)}")

print("\n" + "=" * 80)
