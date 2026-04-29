"""users jadvaliga last_lat, last_lng qo'shish

Revision ID: 0004_user_last_location
Revises: 0003_cart_items
Create Date: 2026-04-27
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_user_last_location"
down_revision: Union[str, None] = "0003_cart_items"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("last_lat", sa.Float(), nullable=True))
    op.add_column("users", sa.Column("last_lng", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "last_lng")
    op.drop_column("users", "last_lat")
