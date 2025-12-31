"""Test ChromaDB query"""
from app.rag.chroma_manager import chroma_manager

print('Initializing ChromaDB...')
chroma_manager.initialize()

print('\nQuerying ChromaDB...')
try:
    result = chroma_manager.query_schemas(
        query_text='How many employees are there?',
        n_results=3
    )
    print(f'Query success! Found {len(result["documents"])} documents')
    for i, doc in enumerate(result["documents"][:2]):
        print(f'  Doc {i+1}: {doc[:100]}...')
except Exception as e:
    print(f'Query error: {type(e).__name__}: {e}')
    import traceback
    traceback.print_exc()
