"""Quick diagnostic - check few-shot and generate one SQL"""
import sys
import os
os.environ['DEPLOYMENT_ENV'] = 'development'

print("Importing modules...")
from app.agents.sql_agent import sql_agent
from app.rag.few_shot_manager import few_shot_manager  
from app.config import settings

print("\n=== FEW-SHOT MANAGER CHECK ===")
print(f"Initialized: {few_shot_manager._initialized}")
has_vs = hasattr(few_shot_manager, 'vectorstore') and few_shot_manager.vectorstore is not None
print(f"Has vectorstore: {has_vs}")

if not has_vs:
    print("\nCRITICAL PROBLEM: Few-shot vectorstore is NULL!")
    print("This means examples are NOT available to the LLM")
    print("The LLM will generate SQL without any examples to learn from")
else:
    print("\nFew-shot vectorstore exists - testing retrieval...")
    try:
        examples = few_shot_manager.get_relevant_examples(
            "show departments with employees", k=1
        )
        print(f"Retrieved {len(examples)} examples")
    except Exception as e:
        print(f"Error retrieving: {e}")

print("\n=== GENERATING SQL ===")
question = "Show me top 5 departments with most employees"
print(f"Question: {question}")

try:
    result = sql_agent.query_and_answer(question)
    print(f"\nResult count: {result.get('result_count', 0)}")
    print(f"\nTables used:")
    for t in result.get('tables_used', []):
        print(f"  - {t}")
    
    print(f"\nGenerated SQL:")
    print(result.get('sql_query', 'NO SQL'))
    
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
