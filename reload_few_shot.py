from app.rag.few_shot_manager import few_shot_manager
from app.database import init_database
from loguru import logger
import sys

# Configure logger
logger.remove()
logger.add(sys.stdout, level="INFO")

def reload_examples():
    print("Initializing database...")
    init_database()
    
    print("Initializing FewShotManager...")
    few_shot_manager.initialize()
    
    print("Reloading examples...")
    few_shot_manager.reload_examples()
    
    print("Done!")

if __name__ == "__main__":
    reload_examples()
