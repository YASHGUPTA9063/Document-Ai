"""batch checklist

Adds the upload-batch column to `documents` and the `batch_checklists` table
behind the Step 3.2 checklist agent.

`documents.batch_id` is nullable with no backfill: documents ingested before
batches existed simply skip the checklist. `batch_checklists.batch_id` carries a
UNIQUE index — the checklist activity relies on it as the mutex that stops every
document in a batch from evaluating the same verdict concurrently.

`db.database.init_db()` applies the same ALTER defensively on startup for SQLite
deployments that do not run Alembic.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-08-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('documents', sa.Column('batch_id', sa.String(), nullable=True))
    op.create_index('ix_documents_batch_id', 'documents', ['batch_id'], unique=False)

    op.create_table(
        'batch_checklists',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('batch_id', sa.String(), nullable=False),
        sa.Column('signature', sa.String(), nullable=False, server_default=''),
        sa.Column('status', sa.String(), nullable=False, server_default='evaluating'),
        sa.Column('required_types', sa.JSON(), nullable=False),
        sa.Column('present_types', sa.JSON(), nullable=False),
        sa.Column('missing_types', sa.JSON(), nullable=False),
        sa.Column('extra_types', sa.JSON(), nullable=False),
        sa.Column('unclassified', sa.JSON(), nullable=False),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('source', sa.String(), nullable=True),
        sa.Column('gate_document_id', sa.String(), nullable=True),
        sa.Column('decision_note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_batch_checklists_batch_id', 'batch_checklists', ['batch_id'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_batch_checklists_batch_id', table_name='batch_checklists')
    op.drop_table('batch_checklists')
    op.drop_index('ix_documents_batch_id', table_name='documents')
    op.drop_column('documents', 'batch_id')
