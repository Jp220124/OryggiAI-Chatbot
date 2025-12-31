from app.agents.sql_agent import RAGSQLAgent
from app.database import init_database
from app.rag.chroma_manager import chroma_manager
from app.rag.few_shot_manager import few_shot_manager
from loguru import logger
import sys

# Configure logger
logger.remove()
logger.add(sys.stdout, level="INFO")

def verify_fix():
    print("Initializing system...")
    init_database()
    chroma_manager.initialize()
    few_shot_manager.initialize()
    
    agent = RAGSQLAgent()
    
    question = "Show me the top 5 departments with the most employees"
    print(f"\nTesting Question: {question}")
    print("-" * 50)
    
    try:
        result = agent.generate_sql(question)
        
        print("\nGenerated SQL:")
        print(result['sql_query'])
        
        if "SectionMaster" in result['sql_query']:
            print("\nSUCCESS: SQL contains SectionMaster join!")
        else:
            print("\nFAILURE: SQL missing SectionMaster join.")
            
    except Exception as e:
        print(f"\nERROR: {e}")

if __name__ == "__main__":
    verify_fix()
