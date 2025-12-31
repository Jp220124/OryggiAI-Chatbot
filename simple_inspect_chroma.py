"""
Simple ChromaDB inspector - no emojis for PowerShell compatibility
"""

import chromadb
from chromadb.config import Settings
import json

# Connect to ChromaDB
client = chromadb.PersistentClient(
    path="./data/chroma_db",
    settings=Settings(anonymized_telemetry=False)
)

collection = client.get_collection(name="database_schema")

# Get all documents
all_data = collection.get()

# Find EmployeeMaster
for doc, meta, doc_id in zip(all_data['documents'], all_data['metadatas'], all_data['ids']):
    if 'EmployeeMaster' in str(meta.get('table_name', '')) or 'EmployeeMaster' in doc_id:
        print("=" * 100)
        print(f"TABLE: {meta.get('table_name', 'Unknown')}")
        print(f"ID: {doc_id}")
        print("=" * 100)
        print()
        print(doc)
        print()
        print("=" * 100)
        print("ANALYSIS:")
        print("=" * 100)
        
        if 'DeptCode' in doc:
            print("[CRITICAL] 'DeptCode' found in schema description (WRONG - column doesn't exist)")
            print()
            print("Lines containing 'DeptCode':")
            for i, line in enumerate(doc.split('\n'), 1):
                if 'DeptCode' in line:
                    print(f"  Line {i}: {line}")
        else:
            print("[OK] 'DeptCode' NOT found in description")
        
        print()
        
        if 'SecCode' in doc:
            print("[OK] 'SecCode' found in description (CORRECT column name)")
            print()
            print("Lines containing 'SecCode':")
            for i, line in enumerate(doc.split('\n'), 1):
                if 'SecCode' in line:
                    print(f"  Line {i}: {line}")
        else:
            print("[WARNING] 'SecCode' NOT found in description")
        
        print()
        print("=" * 100)
        break
