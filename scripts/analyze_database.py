"""
Deep Database Analyzer for OryggiDB
Extracts complete schema: tables, columns, views, relationships
"""

import pyodbc
import json
from datetime import datetime

# Connection string (Windows Auth)
CONNECTION_STRING = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=DESKTOP-UOD2VBS\\MSSQLSERVER2022;"
    "DATABASE=OryggiDB;"
    "Trusted_Connection=yes;"
)

def get_all_tables(cursor):
    """Get all tables in the database"""
    query = """
    SELECT
        t.TABLE_SCHEMA,
        t.TABLE_NAME,
        (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS c WHERE c.TABLE_NAME = t.TABLE_NAME) as ColumnCount
    FROM INFORMATION_SCHEMA.TABLES t
    WHERE t.TABLE_TYPE = 'BASE TABLE'
    ORDER BY t.TABLE_SCHEMA, t.TABLE_NAME
    """
    cursor.execute(query)
    return cursor.fetchall()

def get_all_views(cursor):
    """Get all views in the database"""
    query = """
    SELECT
        v.TABLE_SCHEMA,
        v.TABLE_NAME as VIEW_NAME,
        (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS c WHERE c.TABLE_NAME = v.TABLE_NAME) as ColumnCount
    FROM INFORMATION_SCHEMA.VIEWS v
    ORDER BY v.TABLE_SCHEMA, v.TABLE_NAME
    """
    cursor.execute(query)
    return cursor.fetchall()

def get_table_columns(cursor, schema, table_name):
    """Get all columns for a specific table"""
    query = """
    SELECT
        c.COLUMN_NAME,
        c.DATA_TYPE,
        c.CHARACTER_MAXIMUM_LENGTH,
        c.NUMERIC_PRECISION,
        c.IS_NULLABLE,
        c.COLUMN_DEFAULT,
        c.ORDINAL_POSITION
    FROM INFORMATION_SCHEMA.COLUMNS c
    WHERE c.TABLE_SCHEMA = ? AND c.TABLE_NAME = ?
    ORDER BY c.ORDINAL_POSITION
    """
    cursor.execute(query, (schema, table_name))
    return cursor.fetchall()

def get_primary_keys(cursor, schema, table_name):
    """Get primary key columns for a table"""
    query = """
    SELECT
        kcu.COLUMN_NAME
    FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
    JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
        ON tc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME
    WHERE tc.TABLE_SCHEMA = ?
        AND tc.TABLE_NAME = ?
        AND tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
    ORDER BY kcu.ORDINAL_POSITION
    """
    cursor.execute(query, (schema, table_name))
    return [row[0] for row in cursor.fetchall()]

def get_foreign_keys(cursor, schema, table_name):
    """Get foreign key relationships for a table"""
    query = """
    SELECT
        fk.name AS FK_NAME,
        COL_NAME(fkc.parent_object_id, fkc.parent_column_id) AS FK_COLUMN,
        OBJECT_NAME(fkc.referenced_object_id) AS REFERENCED_TABLE,
        COL_NAME(fkc.referenced_object_id, fkc.referenced_column_id) AS REFERENCED_COLUMN
    FROM sys.foreign_keys fk
    JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
    WHERE OBJECT_SCHEMA_NAME(fk.parent_object_id) = ?
        AND OBJECT_NAME(fk.parent_object_id) = ?
    """
    cursor.execute(query, (schema, table_name))
    return cursor.fetchall()

def get_sample_data(cursor, schema, table_name, limit=3):
    """Get sample data from a table"""
    try:
        query = f"SELECT TOP {limit} * FROM [{schema}].[{table_name}]"
        cursor.execute(query)
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        return columns, rows
    except Exception as e:
        return [], []

def get_row_count(cursor, schema, table_name):
    """Get approximate row count for a table"""
    try:
        query = f"SELECT COUNT(*) FROM [{schema}].[{table_name}]"
        cursor.execute(query)
        return cursor.fetchone()[0]
    except:
        return -1

def get_view_definition(cursor, schema, view_name):
    """Get the SQL definition of a view"""
    try:
        query = """
        SELECT OBJECT_DEFINITION(OBJECT_ID(?))
        """
        full_name = f"{schema}.{view_name}"
        cursor.execute(query, (full_name,))
        result = cursor.fetchone()
        return result[0] if result and result[0] else "Definition not available"
    except Exception as e:
        return f"Error: {str(e)}"

def analyze_database():
    """Main function to analyze the entire database"""
    # Disable printing to console, save to file only
    import sys
    import io

    # Open log file for detailed output
    log_file = open("./data/database_analysis_log.txt", "w", encoding="utf-8")

    def log(msg):
        log_file.write(msg + "\n")
        log_file.flush()

    log("=" * 80)
    log("ORYGGIDB DEEP ANALYSIS - University Database Research")
    log("=" * 80)
    log(f"Analysis started at: {datetime.now()}")
    log("")

    print("Starting database analysis... (output saved to data/database_analysis_log.txt)")

    conn = pyodbc.connect(CONNECTION_STRING)
    cursor = conn.cursor()

    analysis = {
        "database": "OryggiDB",
        "analysis_date": str(datetime.now()),
        "tables": [],
        "views": [],
        "summary": {}
    }

    # ==================== ANALYZE TABLES ====================
    log("\n" + "=" * 80)
    log("PHASE 1: ANALYZING ALL TABLES")
    log("=" * 80)

    tables = get_all_tables(cursor)
    log(f"\nFound {len(tables)} tables\n")
    print(f"Found {len(tables)} tables")

    for idx, (schema, table_name, col_count) in enumerate(tables):
        log(f"\n{'-' * 60}")
        log(f"TABLE: [{schema}].[{table_name}]")
        log(f"{'-' * 60}")
        if idx % 20 == 0:
            print(f"Processing tables... {idx}/{len(tables)}")

        # Get columns
        columns = get_table_columns(cursor, schema, table_name)

        # Get primary keys
        pks = get_primary_keys(cursor, schema, table_name)

        # Get foreign keys
        fks = get_foreign_keys(cursor, schema, table_name)

        # Get row count
        row_count = get_row_count(cursor, schema, table_name)

        log(f"Columns: {len(columns)} | Rows: {row_count:,}")
        log(f"Primary Key: {', '.join(pks) if pks else 'None'}")

        if fks:
            log("Foreign Keys:")
            for fk in fks:
                log(f"  -> {fk[1]} -> {fk[2]}.{fk[3]}")

        log("\nColumns:")
        column_list = []
        for col in columns:
            col_name, data_type, max_len, precision, nullable, default, ordinal = col

            # Format data type
            if max_len and max_len > 0:
                type_str = f"{data_type}({max_len})"
            elif precision:
                type_str = f"{data_type}({precision})"
            else:
                type_str = data_type

            null_str = "NULL" if nullable == "YES" else "NOT NULL"
            pk_marker = " [PK]" if col_name in pks else ""

            log(f"  - {col_name}: {type_str} {null_str}{pk_marker}")

            column_list.append({
                "name": col_name,
                "data_type": type_str,
                "nullable": nullable == "YES",
                "is_primary_key": col_name in pks
            })

        # Store table info
        analysis["tables"].append({
            "schema": schema,
            "name": table_name,
            "full_name": f"[{schema}].[{table_name}]",
            "row_count": row_count,
            "columns": column_list,
            "primary_keys": pks,
            "foreign_keys": [
                {"column": fk[1], "ref_table": fk[2], "ref_column": fk[3]}
                for fk in fks
            ]
        })

    # ==================== ANALYZE VIEWS ====================
    log("\n" + "=" * 80)
    log("PHASE 2: ANALYZING ALL VIEWS")
    log("=" * 80)

    views = get_all_views(cursor)
    log(f"\nFound {len(views)} views\n")
    print(f"Found {len(views)} views")

    for idx, (schema, view_name, col_count) in enumerate(views):
        log(f"\n{'-' * 60}")
        log(f"VIEW: [{schema}].[{view_name}]")
        log(f"{'-' * 60}")
        if idx % 10 == 0:
            print(f"Processing views... {idx}/{len(views)}")

        # Get columns
        columns = get_table_columns(cursor, schema, view_name)

        # Get row count (may be slow for complex views)
        row_count = get_row_count(cursor, schema, view_name)

        # Get view definition
        view_def = get_view_definition(cursor, schema, view_name)

        log(f"Columns: {len(columns)} | Approximate Rows: {row_count:,}")

        log("\nColumns:")
        column_list = []
        for col in columns:
            col_name, data_type, max_len, precision, nullable, default, ordinal = col

            if max_len and max_len > 0:
                type_str = f"{data_type}({max_len})"
            elif precision:
                type_str = f"{data_type}({precision})"
            else:
                type_str = data_type

            log(f"  - {col_name}: {type_str}")

            column_list.append({
                "name": col_name,
                "data_type": type_str
            })

        # Log view definition (truncated)
        if view_def and len(view_def) > 500:
            log(f"\nView Definition (first 500 chars):\n{view_def[:500]}...")
        else:
            log(f"\nView Definition:\n{view_def}")

        # Store view info
        analysis["views"].append({
            "schema": schema,
            "name": view_name,
            "full_name": f"[{schema}].[{view_name}]",
            "row_count": row_count,
            "columns": column_list,
            "definition": view_def[:1000] if view_def else ""
        })

    # ==================== SUMMARY ====================
    log("\n" + "=" * 80)
    log("SUMMARY")
    log("=" * 80)

    analysis["summary"] = {
        "total_tables": len(tables),
        "total_views": len(views),
        "total_columns": sum(len(t["columns"]) for t in analysis["tables"]),
        "tables_with_fks": len([t for t in analysis["tables"] if t["foreign_keys"]])
    }

    log(f"Total Tables: {analysis['summary']['total_tables']}")
    log(f"Total Views: {analysis['summary']['total_views']}")
    log(f"Total Columns: {analysis['summary']['total_columns']}")
    log(f"Tables with Foreign Keys: {analysis['summary']['tables_with_fks']}")

    # Save to JSON
    output_file = "./data/database_analysis.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(analysis, f, indent=2, default=str)

    log(f"\nAnalysis saved to: {output_file}")
    print(f"\n=== ANALYSIS COMPLETE ===")
    print(f"Total Tables: {analysis['summary']['total_tables']}")
    print(f"Total Views: {analysis['summary']['total_views']}")
    print(f"Total Columns: {analysis['summary']['total_columns']}")
    print(f"Results saved to: {output_file}")

    log_file.close()
    cursor.close()
    conn.close()

    return analysis

if __name__ == "__main__":
    analyze_database()
