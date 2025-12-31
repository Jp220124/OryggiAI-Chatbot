"""
Debug Few-Shot Manager
"""
import os
os.environ['DEPLOYMENT_ENV'] = 'development'

from app.rag.few_shot_manager import few_shot_manager
import json

print("Initializing Few-Shot Manager...")
few_shot_manager.initialize()

print(f"\nLoaded Examples: {len(few_shot_manager.examples)}")
print(f"Examples Path: {few_shot_manager.examples_path}")

if len(few_shot_manager.examples) > 0:
    print("\nFirst 3 Examples:")
    for i, ex in enumerate(few_shot_manager.examples[:3]):
        print(f"\nExample {i+1}:")
        print(f"Question: {ex.get('question')}")
        print(f"SQL: {ex.get('sql')}")
        print(f"Tables Used: {ex.get('tables_used')}")
        
    # Check for specific view usage
    view_count = 0
    for ex in few_shot_manager.examples:
        sql = ex.get('sql', '').lower()
        if 'vw_' in sql or 'view_' in sql or 'allemployeeunion' in sql:
            view_count += 1
            
    print(f"\nExamples using views: {view_count}/{len(few_shot_manager.examples)}")
else:
    print("\nNO EXAMPLES LOADED!")

# Check FAISS index
if few_shot_manager.vectorstore:
    print("\nFAISS Index: Initialized")
else:
    print("\nFAISS Index: NOT Initialized")
