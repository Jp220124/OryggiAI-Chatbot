"""Test Google API connectivity"""
import google.generativeai as genai
from app.config import settings

genai.configure(api_key=settings.gemini_api_key)

# Test 1: Embedding
print('Testing Google Embedding...')
try:
    result = genai.embed_content(
        model=settings.google_embedding_model,
        content='Test query',
        task_type='retrieval_document'
    )
    print(f'Embedding success! Length: {len(result["embedding"])}')
except Exception as e:
    print(f'Embedding error: {type(e).__name__}: {e}')

# Test 2: Text generation
print('\nTesting Gemini generation...')
try:
    model = genai.GenerativeModel(settings.gemini_model)
    response = model.generate_content('Say hello')
    print(f'Generation success! Response: {response.text[:50]}')
except Exception as e:
    print(f'Generation error: {type(e).__name__}: {e}')
