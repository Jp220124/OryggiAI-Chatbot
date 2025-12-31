import json
import logging
from app.database import init_database, db_manager

# Suppress logs
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
from loguru import logger
logger.remove()

def export_schema():
    init_database()
    
    schema = {}
    
    try:
        cols = db_manager.execute_query("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'EmployeeMaster' ORDER BY COLUMN_NAME")
        schema['EmployeeMaster'] = [c['COLUMN_NAME'] for c in cols]
    except Exception as e:
        schema['error'] = str(e)

    with open('schema_dump.json', 'w') as f:
        json.dump(schema, f, indent=2)
        
    print("Schema dumped to schema_dump.json")

if __name__ == "__main__":
    export_schema()
