"""Create platform database tables"""
import sys
sys.path.insert(0, "D:\\OryggiAI_Service\\Advance_Chatbot")

from app.database.platform_connection import platform_db

if __name__ == "__main__":
    print("Initializing platform database...")
    platform_db.initialize()
    print("Creating tables...")
    platform_db.create_tables()
    print("Tables created successfully!")
