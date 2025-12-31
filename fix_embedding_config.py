"""
Check and update embedding provider configuration
"""

import os
from dotenv import load_dotenv, set_key

# Load current .env
load_dotenv()

print("=" * 80)
print("CURRENT EMBEDDING CONFIGURATION")
print("=" * 80)

current_provider = os.getenv('EMBEDDING_PROVIDER', 'sentence-transformers')
print(f"EMBEDDING_PROVIDER: {current_provider}")
print(f"EMBEDDING_MODEL: {os.getenv('EMBEDDING_MODEL', 'sentence-transformers/all-MiniLM-L6-v2')}")
print(f"GOOGLE_EMBEDDING_MODEL: {os.getenv('GOOGLE_EMBEDDING_MODEL', 'models/text-embedding-004')}")

print("\n" + "=" * 80)
print("REQUIRED CONFIGURATION FOR THIS APP")
print("=" * 80)
print("Since the schema was indexed with Google embeddings (768 dims),")
print("the app must use Google embeddings for queries to match.")
print()

# Check if .env exists
env_path = ".env"
if not os.path.exists(env_path):
    print(f"⚠️  .env file not found at: {env_path}")
    print("Creating .env from .env.template...")
    
    # Copy template if .env doesn't exist
    if os.path.exists(".env.template"):
        import shutil
        shutil.copy(".env.template", ".env")
        print("✓ Created .env from template")
    else:
        print("❌ .env.template not found either!")
else:
    print(f"✓ .env file exists")

# Update to use Google embeddings
if current_provider != "google":
    print("\n" + "=" * 80)
    print("UPDATING CONFIGURATION")
    print("=" * 80)
    print("Setting EMBEDDING_PROVIDER=google...")
    
    # Update .env file
    set_key(env_path, "EMBEDDING_PROVIDER", "google")
    print("✓ Updated EMBEDDING_PROVIDER to 'google' in .env")
    print()
    print("⚠️  IMPORTANT: You need to restart the application for this change to take effect!")
else:
    print("\n✓ Configuration is already correct (using Google embeddings)")

print("=" * 80)
