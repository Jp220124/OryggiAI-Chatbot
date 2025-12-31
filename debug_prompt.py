"""Debug: Check if few-shot examples are actually being used in the prompt"""
from app.database.connection import init_database
from app.rag.chroma_manager import chroma_manager
from app.rag.few_shot_manager import few_shot_manager
from app.agents.sql_agent import sql_agent

init_database()
chroma_manager.initialize()

question = "Show me the top 5 departments with the most employees"

# Get the few-shot examples that would be retrieved
examples = few_shot_manager.get_relevant_examples(question, n_results=3)

print("Few-shot examples retrieved:")
for i, ex in enumerate(examples, 1):
    print(f"\n{i}. {ex.get('question', 'unknown')}")
    print(f"   SQL: {ex.get('sql',' unknown')}")

# Get schema context
schema_context = chroma_manager.query_schemas(question, n_results=10)

print(f"\n\nSchema contexts retrieved: {len(schema_context['documents'])}")
for i, meta in enumerate(schema_context['metadatas'], 1):
    print(f"  {i}. {meta.get('table_name', 'unknown')}")

# Build the prompt (like the agent does)
prompt = sql_agent._build_prompt(question, schema_context, examples)

# Save the full prompt to a file
with open('full_prompt.txt', 'w', encoding='utf-8') as f:
    f.write(prompt)

print("\n\nFull prompt saved to full_prompt.txt")
print(f"Prompt length: {len(prompt)} characters")

# Check if the correct  pattern is in the examples
if any('SectionMaster' in ex.get('sql', '') for ex in examples):
    print("\n✓ At least one example shows the correct 3-table join with SectionMaster")
else:
    print("\n❌ WARNING: No examples show SectionMaster join!")
