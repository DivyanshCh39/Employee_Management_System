"""Seed default leave type configurations

Revision ID: 002
Revises: 001
Create Date: 2025-01-01 00:01:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text("""
            INSERT INTO leave_type_configs
                (leave_type, max_days_per_year, is_carry_forward_allowed, requires_document, is_active)
            VALUES
                ('SICK',    12,  0, 1, 1),
                ('CASUAL',  12,  0, 0, 1),
                ('EARNED',  15,  1, 0, 1),
                ('UNPAID',  0,   0, 0, 1)
        """)
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "DELETE FROM leave_type_configs "
            "WHERE leave_type IN ('SICK', 'CASUAL', 'EARNED', 'UNPAID')"
        )
    )