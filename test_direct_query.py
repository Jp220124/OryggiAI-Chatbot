"""Direct test of query_database_tool"""
import asyncio
import sys

# Ensure proper encoding for Windows
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

from app.rag import chroma_manager, few_shot_manager
from app.database import init_database

print("Initializing database...")
init_database()

print("Initializing ChromaDB...")
chroma_manager.initialize()

print("Initializing Few-Shot Manager...")
few_shot_manager.initialize()

print("\nImporting sql_agent...")
from app.agents.sql_agent import sql_agent

print("\nTesting sql_agent.generate_sql directly...")
try:
    result = sql_agent.generate_sql(
        question="How many employees are there?",
        user_id="admin"
    )
    print(f"Success! Result: {result}")
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
