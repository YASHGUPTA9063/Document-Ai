import asyncio
import json
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def main():
    engine = create_async_engine("postgresql+asyncpg://postgres:password@localhost:5432/document_ai")
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT documents.doc_type, extracted_data.validated_data FROM extracted_data JOIN documents ON extracted_data.document_id = documents.id WHERE documents.doc_type IN ('bank_statement', 'utility_bill') AND documents.status = 'completed'"))
        rows = result.fetchall()
        for row in rows:
            print(row[0])
            print(json.dumps(row[1], indent=2))
            print("-----")

asyncio.run(main())
