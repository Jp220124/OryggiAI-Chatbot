import pyodbc

conn_str = (
    'DRIVER={ODBC Driver 17 for SQL Server};'
    'SERVER=DESKTOP-UOD2VBS\\MSSQLSERVER2022;'
    'DATABASE=Oryggi;'
    'Trusted_Connection=yes;'
)

conn = pyodbc.connect(conn_str)
cursor = conn.cursor()

# Get employee 14 details
print('=== ECODE 14 Employee ===')
cursor.execute('SELECT Ecode, CorpEmpCode, FName, LName, PresentCardNo FROM EmployeeMaster WHERE Ecode = 14')
row = cursor.fetchone()
if row:
    cols = [d[0] for d in cursor.description]
    print(dict(zip(cols, row)))

# Get employee 15 details
print()
print('=== ECODE 15 Employee ===')
cursor.execute('SELECT Ecode, CorpEmpCode, FName, LName, PresentCardNo FROM EmployeeMaster WHERE Ecode = 15')
row = cursor.fetchone()
if row:
    cols = [d[0] for d in cursor.description]
    print(dict(zip(cols, row)))

# Check Terminal_Authentication table for both
print()
print('=== Terminal_Authentication for Ecode 14 ===')
cursor.execute('SELECT Ecode, TerminalID, AuthenticationID, ScheduleID, Group1, Status FROM Terminal_Authentication WHERE Ecode = 14')
row = cursor.fetchone()
if row:
    cols = [d[0] for d in cursor.description]
    print(dict(zip(cols, row)))

print()
print('=== Terminal_Authentication for Ecode 15 ===')
cursor.execute('SELECT Ecode, TerminalID, AuthenticationID, ScheduleID, Group1, Status FROM Terminal_Authentication WHERE Ecode = 15')
row = cursor.fetchone()
if row:
    cols = [d[0] for d in cursor.description]
    print(dict(zip(cols, row)))

conn.close()
