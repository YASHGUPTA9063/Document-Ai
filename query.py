import sqlite3
conn = sqlite3.connect('backend-v2/doc_workflow.db')
# Check ALL documents including deleted
rows = conn.execute("SELECT id, filename, file_path, status FROM documents ORDER BY created_at DESC").fetchall()
for r in rows:
    print(f"ID: {r[0]}")
    print(f"File: {r[1]}")
    print(f"Path: {r[2]}")
    print(f"Status: {r[3]}")
    print("---")
