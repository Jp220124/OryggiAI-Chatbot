import logging
from app.database import init_database, db_manager

# Suppress logs
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
from loguru import logger
logger.remove()

def list_tables():
    init_database()
    
    print("\n" + "="*50)
    print("Database Tables:")
    print("="*50)
    try:
        tables = db_manager.execute_query("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE' ORDER BY TABLE_NAME")
        for t in tables:
            print(f"- {t['TABLE_NAME']}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    list_tables()
