"""
Quick test to verify the SQL syntax fix is working
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.agents.sql_agent import sql_agent

# Test the _clean_sql method directly
malformed_queries = [
    "SELECT COUNT FROM Vw_TerminalDetail_VMS",
    "SELECT DeviceCount FROM Vw_TerminalDetail_VMS WHERE Active = 1",
    "SELECT COUNT FROM EmployeeMaster",
]

print("Testing SQL Cleaning/Validation:\n")
print("="*80)

for query in malformed_queries:
    print(f"\nOriginal: {query}")
    cleaned = sql_agent._clean_sql(query)
    print(f"Cleaned:  {cleaned}")
    print(f"Fixed: {'✓' if 'COUNT(*)' in cleaned or 'COUNT' not in query else '✗'}")
    print("-"*80)
