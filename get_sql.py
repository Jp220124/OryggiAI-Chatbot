"""Extract just the SQL query"""
from app.database.connection import init_database
from app.rag.chroma_manager import chroma_manager
from app.agents.sql_agent import sql_agent

init_database()
chroma_manager.initialize()

result = sql_agent.generate_sql('Show me the top 5 departments with the most employees')
sql = result['sql_query']

# Write to file
with open('generated_sql.txt', 'w', encoding='utf-8') as f:
    f.write(sql)

print("SQL written to generated_sql.txt")
print()
print(sql)
