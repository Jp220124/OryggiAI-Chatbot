"""
Comprehensive Diagnostic for SQL Generation Issues
Tests the entire SQL generation pipeline to identify root cause
"""

import sys
import os
from loguru import logger

# Configure logger
logger.remove()
logger.add(sys.stderr, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}")

# Set environment
os.environ['DEPLOYMENT_ENV'] = 'development'

from app.agents.sql_agent import sql_agent
from app.rag.few_shot_manager import few_shot_manager
from app.config import settings
from app.database import db_manager

def test_query(question: str):
    """Test a single query and show full diagnostic info"""
    print("\n" + "="*80)
    print(f"TESTING QUERY: {question}")
    print("="*80)
    
    # 1. Check few-shot examples retrieval
    print("\n[1] Checking few-shot examples retrieval...")
    try:
        if hasattr(few_shot_manager, 'vectorstore') and few_shot_manager.vectorstore:
            examples = few_shot_manager.get_relevant_examples(question, k=3)
            print(f"✓ Retrieved {len(examples)} examples")
            for i, ex in enumerate(examples, 1):
                print(f"\n  Example {i}:")
                print(f"    Question: {ex.get('question', 'N/A')[:100]}...")
                print(f"    Has SQL: {'sql_query' in ex}")
        else:
            print("✗ Few-shot manager not initialized or no vectorstore!")
    except Exception as e:
        print(f"✗ Error retrieving examples: {e}")
    
    # 2. Generate SQL and capture full process
    print("\n[2] Generating SQL query...")
    try:
        result = sql_agent.query_and_answer(question)
        
        print(f"\n  Success: {result.get('success')}")
        print(f"  Result Count: {result.get('result_count', 0)}")
        
        sql_query = result.get('sql_query', '')
        print(f"\n  Generated SQL:")
        print("  " + "-"*76)
        for line in sql_query.split('\n'):
            print(f"  {line}")
        print("  " + "-"*76)
        
        # 3. Check tables used
        tables_used = result.get('tables_used', [])
        print(f"\n  Tables Used: {', '.join(tables_used)}")
        
        # 4. Check if using wrong tables
        wrong_tables = ['EmpDepartRole', 'DeptCategoryRelation', 'HolidayDepartmentRelation']
        using_wrong = [t for t in tables_used if t in wrong_tables]
        if using_wrong:
            print(f"  ⚠️  WARNING: Using potentially empty tables: {', '.join(using_wrong)}")
        
        # Check if using correct pattern
        correct_tables = ['EmployeeMaster', 'SectionMaster', 'DeptMaster']
        using_correct = all(t in tables_used for t in correct_tables)
        if using_correct:
            print(f"  ✓ Using correct 3-table join pattern")
        else:
            missing = [t for t in correct_tables if t not in tables_used]
            print(f"  ✗ Missing tables from correct pattern: {', '.join(missing)}")
        
        # 5. Show results preview
        results = result.get('results', [])
        if results:
            print(f"\n  Results Preview (first 3 rows):")
            for i, row in enumerate(results[:3], 1):
                print(f"    Row {i}: {row}")
        else:
            print(f"\n  ✗ NO RESULTS RETURNED")
        
        return result
        
    except Exception as e:
        print(f"✗ Error generating SQL: {e}")
        import traceback
        traceback.print_exc()
        return None

def test_correct_sql():
    """Test the correct SQL pattern manually"""
    print("\n" + "="*80)
    print("TESTING CORRECT SQL PATTERN")
    print("="*80)
    
    correct_sql = """
    SELECT TOP 5
        dm.DeptCode,
        dm.DeptName,
        COUNT(DISTINCT em.Ecode) as EmployeeCount
    FROM EmployeeMaster em
    INNER JOIN SectionMaster sm ON em.SecCode = sm.SecCode
    INNER JOIN DeptMaster dm ON sm.DeptCode = dm.DeptCode
    WHERE em.Status = 'A'
    GROUP BY dm.DeptCode, dm.DeptName
    ORDER BY EmployeeCount DESC
    """
    
    print("\nCorrect SQL Pattern:")
    print("-"*80)
    print(correct_sql)
    print("-"*80)
    
    try:
        result = db_manager.execute_query(correct_sql)
        print(f"\n✓ Correct SQL returned {len(result)} rows")
        if result:
            print("\nResults:")
            for row in result:
                print(f"  {row}")
        return result
    except Exception as e:
        print(f"✗ Error executing correct SQL: {e}")
        return None

def check_few_shot_initialization():
    """Check few-shot manager state"""
    print("\n" + "="*80)
    print("CHECKING FEW-SHOT MANAGER INITIALIZATION")
    print("="*80)
    
    print(f"\nEmbedding Provider: {settings.embedding_provider}")
    print(f"Embedding Model: {settings.embedding_model}")
    print(f"FAISS Index Path: {settings.faiss_index_path}")
    
    print(f"\nFew-shot manager initialized: {few_shot_manager._initialized}")
    print(f"Has vectorstore: {hasattr(few_shot_manager, 'vectorstore') and few_shot_manager.vectorstore is not None}")
    
    if hasattr(few_shot_manager, 'vectorstore') and few_shot_manager.vectorstore:
        # Try to get stats
        try:
            # FAISS doesn't have a direct count, but we can check if it exists
            print(f"Vectorstore type: {type(few_shot_manager.vectorstore)}")
            print("✓ Vectorstore exists")
        except Exception as e:
            print(f"✗ Error checking vectorstore: {e}")
    else:
        print("✗ Vectorstore NOT initialized")
        print("\n⚠️  CRITICAL: Few-shot examples are not available!")
        print("   This means the LLM has NO examples to learn from.")

def main():
    """Run comprehensive diagnostics"""
    print("\n" + "="*80)
    print("COMPREHENSIVE SQL GENERATION DIAGNOSTIC")
    print("="*80)
    
    # Initialize
    print("\n[INITIALIZATION]")
    try:
        sql_agent.initialize()
        print("✓ SQL Agent initialized")
    except Exception as e:
        print(f"✗ SQL Agent initialization failed: {e}")
    
    # Check few-shot manager
    check_few_shot_initialization()
    
    # Test the failing query
    print("\n\n[TESTING FAILING QUERY]")
    test_query("Show me the top 5 departments with the most employees")
    
    # Test correct SQL pattern
    print("\n\n[TESTING CORRECT SQL]")
    test_correct_sql()
    
    # Test other queries
    print("\n\n[TESTING OTHER QUERIES]")
    test_query("List all departments")
    test_query("How many employees are in each department?")
    
    print("\n\n" + "="*80)
    print("DIAGNOSTIC COMPLETE")
    print("="*80)
    print("\nKey Issues to Check:")
    print("1. Is few-shot manager initialized?")
    print("2. Are examples being retrieved?")
    print("3. Is generated SQL using correct tables?")
    print("4. Does correct SQL pattern work?")
    print("="*80)

if __name__ == "__main__":
    main()
