"""KYC image extraction: per-document photo/signature crops + extraction status

Revision ID: e1f2a3b4c5d6
Revises: d0a914027eb4
Create Date: 2026-09-28 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e1f2a3b4c5d6'
down_revision: Union[str, Sequence[str], None] = 'd0a914027eb4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('kyc_applications', sa.Column('form_images_status', sa.String(), nullable=True))
    op.add_column('kyc_documents', sa.Column('photo_path', sa.String(), nullable=True))
    op.add_column('kyc_documents', sa.Column('signature_path', sa.String(), nullable=True))
    op.add_column('kyc_documents', sa.Column('images_status', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('kyc_documents', 'images_status')
    op.drop_column('kyc_documents', 'signature_path')
    op.drop_column('kyc_documents', 'photo_path')
    op.drop_column('kyc_applications', 'form_images_status')
