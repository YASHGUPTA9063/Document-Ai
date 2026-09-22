import sqlite3, json

conn = sqlite3.connect('doc_workflow.db')
r = conn.execute("SELECT documents.doc_type, extracted_data.validated_data FROM extracted_data JOIN documents ON extracted_data.document_id = documents.id WHERE documents.doc_type IN ('bank_statement', 'utility_bill')").fetchall()
print(json.dumps(r, indent=2))
