"""
Debug script to capture the exact SQL being generated for the failing query
"""

import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.agents.sql_agent import sql_agent
from app.database import init_database

def test_query(question: str):
    """Test a query and print the generated SQL"""
    print(f"\n{'='*80}")
    print(f"Testing Query: {question}")
    print(f"{'='*80}\n")
    
    try:
        # Generate SQL
        result = sql_agent.generate_sql(question=question, user_id="admin")
        
        print("GENERATED SQL:")
        print(result['sql_query'])
        print()
        
        # Try to execute it
        print("Attempting to execute...")
        query_result = sql_agent.execute_query(result['sql_query'])
        print(f"Success! Returned {len(query_result)} rows")
        
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Initialize database first
    print("Initializing database...")
    init_database()
    print("Database initialized.\n")
    
    # Test the failing queries
    test_query("List all the terminal")
    test_query("how many devices")
