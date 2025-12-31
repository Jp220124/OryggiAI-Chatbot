"""
Comprehensive View Analysis Script
Categorizes all database views by use case and identifies priority views
"""
import os
os.environ['DEPLOYMENT_ENV'] = 'development'

from app.database import db_manager
import json

print("COMPREHENSIVE DATABASE VIEW ANALYSIS")
print("=" * 80)

# Get all views
query = """
SELECT 
    TABLE_SCHEMA,
    TABLE_NAME,
    VIEW_DEFINITION
FROM INFORMATION_SCHEMA.VIEWS
WHERE TABLE_SCHEMA NOT IN ('sys', 'INFORMATION_SCHEMA')
ORDER BY TABLE_NAME
"""

db_manager.initialize()
views = db_manager.execute_query(query)

print(f"\nTotal views found: {len(views)}\n")

# Categorization keywords
categories = {
    'Employee & Organization': ['employee', 'emp', 'dept', 'department', 'section', 'sec', 'branch', 'company', 'grade', 'designation', 'category'],
    'Attendance': ['attendance', 'present', 'absent', 'leave', 'halfday', 'shift'],
    'Punch Records': ['punch', 'machinepunch', 'rawpunch', 'machine', 'terminal'],
    'Access Control': ['access', 'door', 'group', 'authentication', 'schedule'],
    'Visitor Management': ['visitor', 'vistor', 'vms'],
    'Biometric': ['biometric', 'finger', 'face', 'template'],
    'Contractor': ['contractor', 'contract'],
    'ESIC/PF': ['esic', 'pf', 'esi'],
    'Alerts': ['alert', 'notification'],
    'Other': []
}

# Categorize views
categorized = {cat: [] for cat in categories}

for view in views:
    name = view['TABLE_NAME'].lower()
    definition = (view['VIEW_DEFINITION'] or '').lower()
    
    categorized_flag = False
    for category, keywords in categories.items():
        if category == 'Other':
            continue
        if any(kw in name or kw in definition for kw in keywords):
            categorized[category].append(view['TABLE_NAME'])
            categorized_flag = True
            break
    
    if not categorized_flag:
        categorized['Other'].append(view['TABLE_NAME'])

# Print categorization
print("\nVIEWS BY CATEGORY")
print("=" * 80)

for category, view_list in categorized.items():
    if view_list:
        print(f"\n{category} ({len(view_list)} views):")
        print("-" * 80)
        for v in sorted(view_list):
            print(f"  • {v}")

# Identify priority views
print("\n\n" + "=" * 80)
print("PRIORITY VIEWS ANALYSIS")
print("=" * 80)

priority_views = []

# Check specific important views
important_patterns = [
    ('XXXvw_EmployeeDetail', 'Employee with full org structure and attendance'),
    ('vw_RawPunchDetail', 'Raw punch records detail'),
    ('View_BDW_MPunch', 'Employee + Department + Machine Punch'),
    ('View_ComapnyMaster', 'Employee → Section → Dept → Branch → Company'),
    ('View_EmployeeByUserGroupPolicy', 'Complete employee info with policies'),
    ('View_MPunch', 'Machine punch with employee details'),
    ('View_MPunchV3', 'Machine punch with org hierarchy'),
    ('vw_EmployeeMaster', 'Employee master view if exists'),
    ('View_ForExcelExport', 'Attendance export view'),
]

print("\nChecking for priority views...\n")

for view_name, description in important_patterns:
    matching = [v['TABLE_NAME'] for v in views if v['TABLE_NAME'].lower() == view_name.lower()]
    if matching:
        priority_views.append({
            'name': matching[0],
            'description': description,
            'found': True
        })
        print(f"✓ {matching[0]}")
        print(f"  → {description}")
    else:
        priority_views.append({
            'name': view_name,
            'description': description,
            'found': False
        })
        print(f"✗ {view_name} (NOT FOUND)")
        print(f"  → {description}")

# Additional analysis - find views with most tables joined
print("\n\n" + "=" * 80)
print("VIEWS WITH COMPLEX JOINS (Potentially Useful)")
print("=" * 80)

complex_views = []
for view in views:
    definition = view['VIEW_DEFINITION'] or ''
    join_count = definition.upper().count(' JOIN ')
    if join_count >= 4:  # Views with 4+ joins
        complex_views.append({
            'name': view['TABLE_NAME'],
            'joins': join_count
        })

complex_views.sort(key=lambda x: x['joins'], reverse=True)

print(f"\nTop 10 views with most joins:\n")
for i, cv in enumerate(complex_views[:10], 1):
    print(f"{i:2}. {cv['name']:<50} ({cv['joins']} joins)")

# Save detailed analysis
analysis = {
    'total_views': len(views),
    'categorized': {cat: sorted(vlist) for cat, vlist in categorized.items() if vlist},
    'priority_views': priority_views,
    'complex_views': complex_views[:20]
}

with open('view_analysis.json', 'w') as f:
    json.dump(analysis, f, indent=2)

print("\n\n" + "=" * 80)
print("RECOMMENDATIONS")
print("=" * 80)
print("""
1. INDEX THESE PRIORITY VIEWS:
   - XXXvw_EmployeeDetail (if exists)
   - vw_RawPunchDetail (user mentioned)
   - View_BDW_MPunch
   - View_ComapnyMaster
   - View_EmployeeByUserGroupPolicy
   - View_MPunch/View_MPunchV3

2. CREATE MISSING VIEWS (if needed):
   - Check if critical use cases are covered
   - Consider creating simplified views for common queries

3. UPDATE SCHEMA INDEXING:
   - Include views in schema extraction
   - Prioritize views over base tables
   - Add metadata about view complexity

4. UPDATE FEW-SHOT EXAMPLES:
   - Replace multi-table joins with view queries
   - Add examples for each priority view
""")

print("\nDetailed analysis saved to view_analysis.json")
print("=" * 80)
