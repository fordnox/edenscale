"""drop_fund_team_members

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-07-05 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index(op.f("ix_fund_team_members_user_id"), table_name="fund_team_members")
    op.drop_index(op.f("ix_fund_team_members_fund_id"), table_name="fund_team_members")
    op.drop_table("fund_team_members")


def downgrade() -> None:
    op.create_table(
        "fund_team_members",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("fund_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=150), nullable=True),
        sa.Column("permissions", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["fund_id"], ["funds.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fund_id", "user_id", name="uq_fund_team_member_fund_user"),
    )
    op.create_index(
        op.f("ix_fund_team_members_fund_id"),
        "fund_team_members",
        ["fund_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_fund_team_members_user_id"),
        "fund_team_members",
        ["user_id"],
        unique=False,
    )
