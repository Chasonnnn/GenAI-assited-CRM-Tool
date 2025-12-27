"""merge_appointments_and_main

Revision ID: bd48fc289751
Revises: 0043_appointment_token_expiry, b927a24e41f4
Create Date: 2025-12-21 19:22:42.967820

"""
from typing import Sequence, Union



# revision identifiers, used by Alembic.
revision: str = 'bd48fc289751'
down_revision: Union[str, Sequence[str], None] = ('0043_appointment_token_expiry', 'b927a24e41f4')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
