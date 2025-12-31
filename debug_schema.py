import logging
from app.database import init_database, db_manager

# Suppress logs
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
from loguru import logger
logger.remove()

def check_section_master():
    init_database()
    
    print("\n" + "="*50)
    print("SectionMaster Columns:")
    print("="*50)
    try:
        cols = db_manager.execute_query("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'SectionMaster' ORDER BY COLUMN_NAME")
        for c in cols:
            print(f"- {c['COLUMN_NAME']}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_section_master()
