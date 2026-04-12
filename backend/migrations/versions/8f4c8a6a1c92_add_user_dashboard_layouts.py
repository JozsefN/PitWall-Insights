"""add user dashboard layouts

Revision ID: 8f4c8a6a1c92
Revises: 7c2f0bb3e4f1
Create Date: 2026-04-12 19:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "8f4c8a6a1c92"
down_revision: Union[str, None] = "7c2f0bb3e4f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_dashboard_layouts",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("owner_user_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("audience", sa.String(length=32), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("config_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_user_dashboard_layouts_owner_user_id",
        "user_dashboard_layouts",
        ["owner_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_user_dashboard_layouts_owner_updated",
        "user_dashboard_layouts",
        ["owner_user_id", "updated_at"],
        unique=False,
    )
    op.create_index(
        "ix_user_dashboard_layouts_owner_audience",
        "user_dashboard_layouts",
        ["owner_user_id", "audience"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_user_dashboard_layouts_owner_audience", table_name="user_dashboard_layouts")
    op.drop_index("ix_user_dashboard_layouts_owner_updated", table_name="user_dashboard_layouts")
    op.drop_index("ix_user_dashboard_layouts_owner_user_id", table_name="user_dashboard_layouts")
    op.drop_table("user_dashboard_layouts")
