"""document split columns

Adds the multi-document packet splitting columns to `documents` (Step 1.5).
Every column is nullable or defaulted, so this is a purely additive change with
no backfill. `db.database.init_db()` applies the same ALTERs defensively on
startup for SQLite deployments that do not run Alembic.

Revision ID: a1b2c3d4e5f6
Revises: 4148cc8ec19d
Create Date: 2026-08-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '4148cc8ec19d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('documents', sa.Column('parent_document_id', sa.String(), nullable=True))
    op.add_column('documents', sa.Column('page_range', sa.String(), nullable=True))
    op.add_column('documents', sa.Column('split_doc_type_hint', sa.String(), nullable=True))
    op.add_column('documents', sa.Column('split_confidence', sa.Float(), nullable=True))
    op.add_column(
        'documents',
        sa.Column('is_split_parent', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column('documents', sa.Column('split_manifest', sa.JSON(), nullable=True))
    op.create_index(
        'ix_documents_parent_document_id', 'documents', ['parent_document_id'], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_documents_parent_document_id', table_name='documents')
    op.drop_column('documents', 'split_manifest')
    op.drop_column('documents', 'is_split_parent')
    op.drop_column('documents', 'split_confidence')
    op.drop_column('documents', 'split_doc_type_hint')
    op.drop_column('documents', 'page_range')
    op.drop_column('documents', 'parent_document_id')
