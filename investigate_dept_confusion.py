"""
Investigation: Why RAG generates DeptCode instead of SecCode
Direct ChromaDB inspection without using embedding functions
"""

import chromadb
from chromadb.config import Settings
from loguru import logger
import sys
import os

# Configure loguru to stdout
logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>")

print("=" * 80)
print("INVESTIGATING: DeptCode vs SecCode Confusion")
print("=" * 80)

# Initialize ChromaDB client directly (no embedding function needed for reading)
chroma_dir = "./data/chroma_db"
if not os.path.exists(chroma_dir):
    print(f"\n❌ ChromaDB directory not found: {chroma_dir}")
    print("   Please make sure the vector database has been indexed first.")
    sys.exit(1)

client = chromadb.PersistentClient(
    path=chroma_dir,
    settings=Settings(anonymized_telemetry=False)
)

# Get the collection
try:
    collection = client.get_collection(name="database_schema")
    print(f"\n✓ Connected to ChromaDB collection: database_schema")
except Exception as e:
    print(f"\n❌ Failed to get collection: {e}")
    sys.exit(1)



# Get collection stats
count = collection.count()
print(f"\n📊 Collection Stats:")
print(f"   Total documents: {count}")

print("\n" + "=" * 80)
print("TEST 1: Finding EmployeeMaster table description")
print("=" * 80)

# Get all documents
all_data = collection.get()

# Find EmployeeMaster
employee_master_doc = None
employee_master_meta = None

for doc, meta, doc_id in zip(all_data['documents'], all_data['metadatas'], all_data['ids']):
    table_name = meta.get('table_name', '')
    if 'EmployeeMaster' in table_name or 'EmployeeMaster' in doc_id:
        employee_master_doc = doc
        employee_master_meta = meta
        print(f"\n✓ Found EmployeeMaster document!")
        print(f"   ID: {doc_id}")
        print(f"   Metadata: {meta}")
        break

if not employee_master_doc:
    print("\n❌ EmployeeMaster table not found in vector database!")
    print(f"   Available table IDs: {all_data['ids'][:10]}")
    sys.exit(1)

print("\n" + "=" * 80)
print("TEST 2: Analyzing EmployeeMaster Schema Description")
print("=" * 80)

print("\n📄 Full Enriched Description:")
print("-" * 80)
print(employee_master_doc)
print("-" * 80)

print("\n" + "=" * 80)
print("TEST 3: Root Cause Analysis")
print("=" * 80)

# Check for problematic content
print("\n🔍 Searching for column name references...")

issues_found = []

if 'DeptCode' in employee_master_doc:
    print("\n   ❌ CRITICAL ISSUE FOUND: 'DeptCode' appears in the description!")
    print("      This column does NOT exist in the actual table.")
    
    # Find all occurrences
    lines = employee_master_doc.split('\n')
    for i, line in enumerate(lines, 1):
        if 'DeptCode' in line:
            print(f"      Line {i}: {line.strip()}")
            issues_found.append(f"DeptCode mentioned on line {i}")
else:
    print("   ✓ 'DeptCode' NOT found in description (good)")

if 'SecCode' in employee_master_doc:
    print("\n   ✓ 'SecCode' found in description (correct column name)")
    lines = employee_master_doc.split('\n')
    for i, line in enumerate(lines, 1):
        if 'SecCode' in line:
            print(f"      Line {i}: {line.strip()}")
else:
    print("\n   ⚠️  'SecCode' NOT found in description")
    print("      This is a problem - the LLM enrichment might not have captured this column!")
    issues_found.append("SecCode not mentioned in enriched description")

# Check for department-related terms
dept_terms = ['department', 'Department', 'dept', 'Dept', 'section', 'Section']
print("\n   🔍 Checking for department-related terminology:")
for term in dept_terms:
    if term in employee_master_doc:
        print(f"      Found '{term}':")
        lines = employee_master_doc.split('\n')
        for i, line in enumerate(lines, 1):
            if term in line:
                print(f"         Line {i}: {line.strip()}")

print("\n" + "=" * 80)
print("TEST 4: Check All Tables for DeptCode References")
print("=" * 80)

deptcode_tables = []
for doc, meta, doc_id in zip(all_data['documents'], all_data['metadatas'], all_data['ids']):
    if 'DeptCode' in doc:
        table_name = meta.get('table_name', doc_id)
        deptcode_tables.append(table_name)
        print(f"   ⚠️  Found DeptCode in: {table_name}")

if not deptcode_tables:
    print("   ✓ No tables have DeptCode in their descriptions")

print("\n" + "=" * 80)
print("INVESTIGATION COMPLETE")
print("=" * 80)

print("\n" + "=" * 80)
print("📝 DIAGNOSIS SUMMARY")
print("=" * 80)

if issues_found:
    print("\n❌ Issues Detected:")
    for idx, issue in enumerate(issues_found, 1):
        print(f"   {idx}. {issue}")
    
    print("\n💡 Recommended Actions:")
    print("   1. Re-index the schema with accurate column information")
    print("   2. Check if the LLM enrichment is hallucinating column names")
    print("   3. Verify that schema_dump.json is being used correctly")
    print("   4. Consider adding validation to prevent non-existent columns")
else:
    print("\n✓ No obvious issues detected in the schema description")
    print("   The problem might be in how the LLM interprets the context")
    print("   or how queries are being embedded for retrieval.")

print("\n" + "=" * 80)
