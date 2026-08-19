import sqlite3, json, os

conn = sqlite3.connect('doc_workflow.db')
c = conn.cursor()

# Get a child document ID
c.execute("SELECT id, file_path FROM documents WHERE parent_document_id IS NOT NULL AND status='completed' LIMIT 1")
row = c.fetchone()
if row:
    doc_id, file_path = row
    print(f"Child doc ID: {doc_id}")
    print(f"File path: {file_path}")
    print(f"File exists: {os.path.exists(file_path)}")
else:
    print("No child documents found")

conn.close()
