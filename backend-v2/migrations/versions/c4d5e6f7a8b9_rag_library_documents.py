"""rag library documents

Tracks each uploaded document's copy in the Mistral document library that the
RAG chat searches — the library-side document id and its indexing status.

Revision ID: c4d5e6f7a8b9
Revises: a3b4c5d6e7f8
Create Date: 2026-10-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4d5e6f7a8b9'
down_revision: Union[str, Sequence[str], None] = 'a3b4c5d6e7f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'library_documents',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('document_id', sa.String(), nullable=False),
        sa.Column('library_id', sa.String(), nullable=True),
        sa.Column('mistral_document_id', sa.String(), nullable=True),
        sa.Column('filename', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_library_documents_document_id'), 'library_documents', ['document_id'], unique=True)
    op.create_index(op.f('ix_library_documents_mistral_document_id'), 'library_documents', ['mistral_document_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_library_documents_mistral_document_id'), table_name='library_documents')
    op.drop_index(op.f('ix_library_documents_document_id'), table_name='library_documents')
    op.drop_table('library_documents')
