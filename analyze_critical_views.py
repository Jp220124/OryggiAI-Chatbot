"""
Deep Analysis of Critical Database Views
Analyzes the 9 specific views identified as very important by the user
"""
import os
os.environ['DEPLOYMENT_ENV'] = 'development'

from app.database import db_manager
import json

print("DEEP ANALYSIS OF CRITICAL DATABASE VIEWS")
print("=" * 80)

# The 9 critical views to analyze
critical_views = [
    'vw_RawPunchDetail',
    'AllEmployeeUnion',
    'View_Contractor_Detail',
    'View_Employee_Terminal_Authentication_Relation',
    'View_Visitor_EnrollmentDetail',
    'vw_EmployeeMaster_Vms',
    'Vw_TerminalDetail_VMS',
    'vw_VisitorBasicDetail',
    'View_EmployeeByUserGroupPolicy'
]

db_manager.initialize()

detailed_analysis = {}

for view_name in critical_views:
    print(f"\n{'='*80}")
    print(f"ANALYZING: {view_name}")
    print('='*80)
    
    analysis = {
        'view_name': view_name,
        'exists': False,
        'columns': [],
        'column_count': 0,
        'sample_data_available': False,
        'view_definition': None,
        'base_tables': []
    }
    
    # Check if view exists and get definition
    view_query = """
        SELECT VIEW_DEFINITION
        FROM INFORMATION_SCHEMA.VIEWS
        WHERE TABLE_NAME = ? AND TABLE_SCHEMA = 'dbo'
    """
    
    try:
        result = db_manager.execute_query(view_query, (view_name,))
        if result:
            analysis['exists'] = True
            analysis['view_definition'] = result[0].get('VIEW_DEFINITION', '')
            print(f"\u2713 View exists")
        else:
            print(f"\u2717 View NOT FOUND")
            detailed_analysis[view_name] = analysis
            continue
    except Exception as e:
        print(f"\u2717 Error checking view: {e}")
        detailed_analysis[view_name] = analysis
        continue
    
    # Get columns
    columns_query = """
        SELECT 
            COLUMN_NAME,
            DATA_TYPE,
            CHARACTER_MAXIMUM_LENGTH,
            IS_NULLABLE
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = ? AND TABLE_SCHEMA = 'dbo'
        ORDER BY ORDINAL_POSITION
    """
    
    try:
        columns = db_manager.execute_query(columns_query, (view_name,))
        analysis['columns'] = []
        
        print(f"\nColumns ({len(columns)} total):")
        print("-" * 80)
        
        for col in columns:
            col_info = {
                'name': col['COLUMN_NAME'],
                'type': col['DATA_TYPE'],
                'max_length': col['CHARACTER_MAXIMUM_LENGTH'],
                'nullable': col['IS_NULLABLE'] == 'YES'
            }
            analysis['columns'].append(col_info)
            
            # Print column info
            type_str = col['DATA_TYPE']
            if col['CHARACTER_MAXIMUM_LENGTH']:
                type_str += f"({col['CHARACTER_MAXIMUM_LENGTH']})"
            nullable_str = "NULL" if col['IS_NULLABLE'] == 'YES' else "NOT NULL"
            print(f"  {col['COLUMN_NAME']:<40} {type_str:<20} {nullable_str}")
        
        analysis['column_count'] = len(columns)
        
    except Exception as e:
        print(f"\u2717 Error getting columns: {e}")
    
    # Try to get sample data (just count, don't retrieve all)
    try:
        count_query = f"SELECT COUNT(*) as cnt FROM dbo.{view_name}"
        result = db_manager.execute_query(count_query)
        if result:
            row_count = result[0].get('cnt', 0)
            analysis['sample_data_available'] = True
            analysis['row_count'] = row_count
            print(f"\n\u2713 View contains {row_count:,} rows")
    except Exception as e:
        print(f"\n\u2717 Could not get row count: {e}")
    
    # Extract base tables from definition
    if analysis['view_definition']:
        import re
        pattern = r'(?:FROM|JOIN)\s+(?:dbo\.)?([\w]+)'
        tables = re.findall(pattern, analysis['view_definition'], re.IGNORECASE)
        excluded = {'SELECT', 'WHERE', 'GROUP', 'ORDER', 'HAVING', 'UNION', 'VALUES', 'CASE', 'WHEN', 'THEN', 'ELSE', 'END', 'AS', 'ON'}
        unique_tables = list(set([t for t in tables if t.upper() not in excluded and not t.startswith('vw_') and not t.startswith('View_')]))
        analysis['base_tables'] = unique_tables
        
        print(f"\nBase Tables ({len(unique_tables)}):")
        for table in sorted(unique_tables):
            print(f"  - {table}")
    
    # Get first 3 rows as sample
    try:
        sample_query = f"SELECT TOP 3 * FROM dbo.{view_name}"
        sample_data = db_manager.execute_query(sample_query)
        if sample_data:
            print(f"\nSample Data (first row):")
            print("-" * 80)
            first_row = sample_data[0]
            for key, value in list(first_row.items())[:10]:  # Show first 10 columns
                value_str = str(value)[:50] if value else 'NULL'
                print(f"  {key}: {value_str}")
            if len(first_row) > 10:
                print(f"  ... and {len(first_row) - 10} more columns")
    except Exception as e:
        print(f"\n\u2717 Could not get sample data: {e}")
    
    detailed_analysis[view_name] = analysis

# Save detailed analysis
with open('critical_views_analysis.json', 'w') as f:
    json.dump(detailed_analysis, f, indent=2, default=str)

print("\n\n" + "="*80)
print("SUMMARY OF CRITICAL VIEWS")
print("="*80)

for view_name, analysis in detailed_analysis.items():
    if analysis['exists']:
        print(f"\n\u2713 {view_name}")
        print(f"   Columns: {analysis['column_count']}")
        print(f"   Rows: {analysis.get('row_count', 'Unknown'):,}" if 'row_count' in analysis else "   Rows: Unknown")
        print(f"   Base Tables: {', '.join(analysis['base_tables'][:5])}")
    else:
        print(f"\n\u2717 {view_name} - NOT FOUND")

print("\n\nDetailed analysis saved to: critical_views_analysis.json")
print("="*80)
