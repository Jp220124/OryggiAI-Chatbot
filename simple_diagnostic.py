"""Simple diagnostic to find SQL generation issues"""
import sys
import os
os.environ['DEPLOYMENT_ENV'] = 'development'

from app.agents.sql_agent import sql_agent
from app.rag.few_shot_manager import few_shot_manager  
from app.config import settings

print("="*60)
print("SQL GENERATION DIAGNOSTIC")
print("="*60)

# Initialize
sql_agent.initialize()

# Check few-shot manager
print("\n[1] FEW-SHOT MANAGER STATUS")
print(f"Initialized: {few_shot_manager._initialized}")
print(f"Has vectorstore: {hasattr(few_shot_manager, 'vectorstore') and few_shot_manager.vectorstore is not None}")
print(f"Embedding provider: {settings.embedding_provider}")

# Test example retrieval
print("\n[2] TESTING EXAMPLE RETRIEVAL")
question = "Show me top 5 departments with most employees"
try:
    if few_shot_manager.vectorstore:
        examples = few_shot_manager.get_relevant_examples(question, k=2)
        print(f"Retrieved {len(examples)} examples")
        for i, ex in enumerate(examples, 1):
            print(f"\n  Example {i}:")
            q = ex.get('question', 'N/A')
            print(f"    Q: {q[:80]}...")
            if 'sql_query' in ex:
                sql = ex['sql_query'].replace('\n', ' ')[:100]
                print(f"    SQL: {sql}...")
    else:
        print("ERROR: No vectorstore! Examples not loaded!")
except Exception as e:
    print(f"ERROR: {e}")

# Generate SQL
print(f"\n[3] GENERATING SQL FOR: {question}")
try:
    result = sql_agent.query_and_answer(question)
    print(f"Success: {result.get('success')}")
    print(f"Result count: {result.get('result_count', 0)}")
    
    sql = result.get('sql_query', '')
    print("\nGenerated SQL:")
    print(sql)
    
    tables = result.get('tables_used', [])
    print(f"\nTables used: {', '.join(tables)}")
    
    # Check for wrong tables
    wrong = ['EmpDepartRole', 'DeptCategoryRelation']
    bad_tables = [t for t in tables if t in wrong]
    if bad_tables:
        print(f"WARNING: Using empty tables: {bad_tables}")
    
    # Check for correct pattern
    if 'SectionMaster' in tables:
        print("GOOD: Using SectionMaster (correct pattern)")
    else:
        print("BAD: Missing SectionMaster (incorrect pattern)")
        
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*60)
