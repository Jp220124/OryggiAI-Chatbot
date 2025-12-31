"""Add gateway columns to tenant_databases table"""

from sqlalchemy import create_engine, text
from app.config import settings

engine = create_engine(settings.platform_database_url)

print('Adding gateway columns to tenant_databases table...')

with engine.connect() as conn:
    try:
        conn.execute(text("ALTER TABLE tenant_databases ADD connection_mode NVARCHAR(50) DEFAULT 'auto'"))
        print('  Added connection_mode column')
    except Exception as e:
        print(f'  connection_mode: {e}')

    try:
        conn.execute(text('ALTER TABLE tenant_databases ADD gateway_api_key_id UNIQUEIDENTIFIER NULL'))
        print('  Added gateway_api_key_id column')
    except Exception as e:
        print(f'  gateway_api_key_id: {e}')

    try:
        conn.execute(text('ALTER TABLE tenant_databases ADD gateway_last_heartbeat DATETIME NULL'))
        print('  Added gateway_last_heartbeat column')
    except Exception as e:
        print(f'  gateway_last_heartbeat: {e}')

    conn.commit()
    print('Done!')
