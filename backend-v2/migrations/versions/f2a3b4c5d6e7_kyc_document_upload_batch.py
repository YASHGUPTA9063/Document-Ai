"""kyc document upload batch

Adds `kyc_documents.upload_batch` so the documents added together in one KYC
upload can be told apart from earlier ones — the user picks the document to
verify against from the latest batch. The ID type is no longer chosen at upload
time, so `kyc_documents.doc_type` becomes nullable.

Rows from before this migration have no batch; the UI treats them as one.

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-09-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f2a3b4c5d6e7'
down_revision: Union[str, Sequence[str], None] = 'e1f2a3b4c5d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('kyc_documents', sa.Column('upload_batch', sa.String(), nullable=True))
    op.alter_column('kyc_documents', 'doc_type', existing_type=sa.String(), nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("UPDATE kyc_documents SET doc_type = 'id_document' WHERE doc_type IS NULL")
    op.alter_column('kyc_documents', 'doc_type', existing_type=sa.String(), nullable=False)
    op.drop_column('kyc_documents', 'upload_batch')
