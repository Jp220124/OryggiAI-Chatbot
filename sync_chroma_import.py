"""
Import database_schema collection from JSON export
"""
import chromadb
from chromadb.config import Settings
import json
import os
import google.generativeai as genai
from chromadb import EmbeddingFunction, Embeddings, Documents

# Configure Google API
genai.configure(api_key='AIzaSyCoAjcg-PU-MUAgDPTRUXblqp6eBut9nDo')

class GoogleEmbeddingFunction(EmbeddingFunction):
    def __init__(self):
        self.model_name = 'models/text-embedding-004'

    def __call__(self, input: Documents) -> Embeddings:
        embeddings = []
        for text in input:
            result = genai.embed_content(
                model=self.model_name,
                content=text,
                task_type='retrieval_document'
            )
            embeddings.append(result['embedding'])
        return embeddings

def main():
    print("Starting ChromaDB import...")

    # Connect to ChromaDB
    client = chromadb.PersistentClient(
        path='./data/chroma_db',
        settings=Settings(anonymized_telemetry=False)
    )

    # Delete existing collection
    try:
        client.delete_collection('database_schema')
        print('Deleted existing database_schema collection')
    except Exception as e:
        print(f'No existing collection to delete: {e}')

    # Load export data
    with open('data/database_schema_export.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f'Loaded {len(data["ids"])} documents to import')

    # Create new collection with embedding function
    embedding_fn = GoogleEmbeddingFunction()
    col = client.create_collection(
        'database_schema',
        embedding_function=embedding_fn,
        metadata={"description": "Database schema embeddings for RAG"}
    )

    # Import in batches
    batch_size = 25  # Smaller batches to avoid API limits
    total_batches = (len(data['ids']) + batch_size - 1) // batch_size

    for i in range(0, len(data['ids']), batch_size):
        batch_num = i // batch_size + 1
        batch_ids = data['ids'][i:i+batch_size]
        batch_docs = data['documents'][i:i+batch_size]
        batch_meta = data['metadatas'][i:i+batch_size]

        try:
            col.add(ids=batch_ids, documents=batch_docs, metadatas=batch_meta)
            print(f'Batch {batch_num}/{total_batches}: Imported {len(batch_ids)} documents')
        except Exception as e:
            print(f'Batch {batch_num} error: {e}')

    print(f'\nFinal count: {col.count()} embeddings')
    print('Import complete!')

if __name__ == '__main__':
    main()
