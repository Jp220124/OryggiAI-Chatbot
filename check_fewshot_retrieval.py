"""Check if few-shot examples are being retrieved for department queries"""
from app.database.connection import init_database
from app.rag.chroma_manager import chroma_manager
from app.rag.few_shot_manager import few_shot_manager

init_database()
chroma_manager.initialize()

question = "Show me the top 5 departments with the most employees"

print(f"Question: {question}")
print("=" * 80)

# Check what few-shot examples are retrieved
examples = few_shot_manager.get_relevant_examples(question, n_results=5)

print(f"\nRetrieved {len(examples)} few-shot examples:")
for i, ex in enumerate(examples, 1):
    print(f"\n{i}. ID: {ex.get('id', 'unknown')}")
    print(f"   Category: {ex.get('category', 'unknown')}")
    print(f"   Question: {ex.get('question', 'unknown')}")
    print(f"   SQL: {ex.get('sql', 'unknown')[:100]}...")

print("\n" + "=" * 80)
print("Expected: Should retrieve ex_004 (top 5 departments example)")
print("=" * 80)
