"""Check if few-shot manager is initialized properly"""
from app.database.connection import init_database
from app.rag.few_shot_manager import few_shot_manager

init_database()

print("Checking FewShotManager status...")
print(f"Initialized: {few_shot_manager._initialized}")

if not few_shot_manager._initialized:
    print("\n⚠️  Few-shot manager NOT initialized!")
    print("Initializing now...")
    few_shot_manager.initialize()
    print(f"✓ Initialized: {few_shot_manager._initialized}")

stats = few_shot_manager.get_stats()
print(f"\nStats: {stats}")

# Try getting relevant examples
question = "Show me the top 5 departments with the most employees"
examples = few_shot_manager.get_relevant_examples(question, n_results=5)

print(f"\nRetrieved {len(examples)} examples for: '{question}'")
for i, ex in enumerate(examples, 1):
    print(f"\n{i}. {ex.get('question')}")
    print(f"   SQL: {ex.get('sql')[:80]}...")
    if 'SectionMaster' in ex.get('sql', ''):
        print("   ✓ Contains SectionMaster (correct pattern!)")
