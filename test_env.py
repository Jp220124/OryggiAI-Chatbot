import sys
sys.path.insert(0, '.')
from app.config import get_settings

settings = get_settings()
print("GEMINI_MODEL:", repr(settings.gemini_model))
print("DB_SERVER:", repr(settings.db_server))
print("DB_INSTANCE:", repr(settings.db_instance))
