"""
Extract Critical View Definitions from database_views.txt
"""

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

print("EXTRACTING CRITICAL VIEW DEFINITIONS")
print("=" * 80)

# Read the database_views.txt file
with open('database_views.txt', 'r', encoding='utf-8') as f:
    content = f.read()

# Split by view separators
views_content = content.split('================================================================================')

view_definitions = {}

for view_name in critical_views:
    print(f"\nSearching for: {view_name}")
    
    # Find the view in the content
    for section in views_content:
        if f'View: dbo.{view_name}' in section:
            # Extract the definition part
            lines = section.strip().split('\n')
            if len(lines) > 2:
                definition = '\n'.join(lines[2:])  # Skip the "View: dbo.ViewName" and "Definition:" lines
                view_definitions[view_name] = definition
                print(f"  \u2713 Found - {len(definition)} characters")
                
                # Save individual view file
                with open(f'view_def_{view_name}.sql', 'w', encoding='utf-8') as vf:
                    vf.write(f"-- View: {view_name}\n")
                    vf.write(f"-- {'-' * 78}\n\n")
                    vf.write(definition)
                
                break
    else:
        print(f"  \u2717 NOT FOUND")
        view_definitions[view_name] = None

# Create comprehensive analysis document
analysis_doc = []
analysis_doc.append("# CRITICAL DATABASE VIEWS - DETAILED ANALYSIS\n")
analysis_doc.append("=" * 80 + "\n\n")

for view_name in critical_views:
    analysis_doc.append(f"\n## {view_name}\n")
    analysis_doc.append("-" * 80 + "\n")
    
    if view_definitions[view_name]:
        # Analyze the definition
        definition = view_definitions[view_name]
        
        # Count JOINs
        joins = definition.upper().count(' JOIN ')
        
        # Extract table references
        import re
        pattern = r'(?:FROM|JOIN)\s+(?:dbo\.)?([\w]+)'
        tables = re.findall(pattern, definition, re.IGNORECASE)
        excluded = {'SELECT', 'WHERE', 'GROUP', 'ORDER', 'HAVING', 'UNION', 'VALUES'}
        unique_tables = list(set([t for t in tables if t.upper() not in excluded]))
        
        analysis_doc.append(f"\n**Complexity:**\n")
        analysis_doc.append(f"- JOINs: {joins}\n")
        analysis_doc.append(f"- Base Tables: {len(unique_tables)}\n\n")
        
        analysis_doc.append(f"**Tables Referenced:**\n")
        for table in sorted(unique_tables):
            analysis_doc.append(f"  - {table}\n")
        
        analysis_doc.append(f"\n**SQL Definition (truncated to 500 chars):**\n")
        analysis_doc.append(f"```sql\n{definition[:500]}...\n```\n")
        
        analysis_doc.append(f"\n**Full definition saved to:** `view_def_{view_name}.sql`\n")
    else:
        analysis_doc.append("\n**STATUS:** View definition NOT FOUND in database_views.txt\n")
    
    analysis_doc.append("\n\n")

# Save analysis
with open('CRITICAL_VIEWS_ANALYSIS.md', 'w', encoding='utf-8') as f:
    f.writelines(analysis_doc)

print("\n\n" + "=" * 80)
print("EXTRACTION COMPLETE")
print("=" * 80)
print(f"\nFound: {sum(1 for v in view_definitions.values() if v is not None)}/{len(critical_views)} views")
print(f"\nGenerated files:")
print(f"  - CRITICAL_VIEWS_ANALYSIS.md (comprehensive analysis)")
for view_name in critical_views:
    if view_definitions[view_name]:
        print(f"  - view_def_{view_name}.sql")
print("=" * 80)
