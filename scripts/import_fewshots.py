"""
Import few-shot examples from JSON file into platform database
"""
import json
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import uuid

# Configuration
TENANT_DB_ID = "17E8126D-D8C6-468C-83BB-72DE92397C3C"  # Oryggi database ID
JSON_FILE = "./data/few_shot_examples.json"

# Platform database connection
from urllib.parse import quote_plus
_password = quote_plus("P@ssw0rd123!Strong")
PLATFORM_DB_URL = os.getenv(
    "PLATFORM_DATABASE_URL",
    f"mssql+pyodbc://oryggi_test_user:{_password}@localhost/OryggiAI_Platform?driver=ODBC+Driver+17+for+SQL+Server&TrustServerCertificate=yes"
)

def main():
    print(f"Importing few-shot examples for tenant_db_id: {TENANT_DB_ID}")

    # Load JSON file
    with open(JSON_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    examples = data.get("examples", [])
    print(f"Found {len(examples)} examples in JSON file")

    # Connect to database
    engine = create_engine(PLATFORM_DB_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Clear existing few-shot examples for this tenant
        delete_sql = text("""
            DELETE FROM few_shot_examples
            WHERE tenant_db_id = :tenant_db_id
        """)
        result = session.execute(delete_sql, {"tenant_db_id": TENANT_DB_ID})
        print(f"Deleted {result.rowcount} existing records")

        # Insert new examples
        insert_sql = text("""
            INSERT INTO few_shot_examples (
                id, tenant_db_id, question, sql_query, explanation,
                module, category, complexity, tables_used,
                is_verified, is_active, source, generated_by,
                created_at, updated_at
            ) VALUES (
                :id, :tenant_db_id, :question, :sql_query, :explanation,
                :module, :category, :complexity, :tables_used,
                :is_verified, :is_active, :source, :generated_by,
                GETDATE(), GETDATE()
            )
        """)

        count = 0
        for ex in examples:
            params = {
                "id": str(uuid.uuid4()),
                "tenant_db_id": TENANT_DB_ID,
                "question": ex.get("question", ""),
                "sql_query": ex.get("sql", ""),
                "explanation": ex.get("explanation", ""),
                "module": ex.get("category", "general"),
                "category": ex.get("category", "general"),
                "complexity": "medium",
                "tables_used": json.dumps(ex.get("tables_used", [])),
                "is_verified": True,  # These are pre-verified examples
                "is_active": True,
                "source": "manual",
                "generated_by": "admin"
            }
            session.execute(insert_sql, params)
            count += 1

            if count % 50 == 0:
                print(f"  Inserted {count} records...")

        session.commit()
        print(f"\nSuccessfully imported {count} few-shot examples!")

        # Verify count
        verify_sql = text("""
            SELECT COUNT(*) FROM few_shot_examples
            WHERE tenant_db_id = :tenant_db_id
        """)
        result = session.execute(verify_sql, {"tenant_db_id": TENANT_DB_ID})
        final_count = result.scalar()
        print(f"Verification: {final_count} records in database")

    except Exception as e:
        session.rollback()
        print(f"Error: {e}")
        raise
    finally:
        session.close()

if __name__ == "__main__":
    main()
