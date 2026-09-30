"""kyc applicant contact details

Adds the extra applicant details read off the KYC form — gender, nationality,
passport number, driving license number, email and contact number — so the
review step can show and edit them.

Revision ID: a3b4c5d6e7f8
Revises: f2a3b4c5d6e7
Create Date: 2026-09-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3b4c5d6e7f8'
down_revision: Union[str, Sequence[str], None] = 'f2a3b4c5d6e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

COLUMNS = (
    'gender', 'nationality', 'passport_number',
    'driving_license_number', 'email', 'contact_number',
)


def upgrade() -> None:
    """Upgrade schema."""
    for name in COLUMNS:
        op.add_column('kyc_applications', sa.Column(name, sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    for name in reversed(COLUMNS):
        op.drop_column('kyc_applications', name)
