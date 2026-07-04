"""drop_users_organization_id

Memberships (user_organization_memberships) are the source of truth for who
belongs to an organization and with what role; the legacy single-org
``users.organization_id`` column is no longer read anywhere. Backfill any
membership rows still missing from legacy data, then drop the column.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-07-04 19:00:00.000000

"""
import uuid

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = 'd4e5f6a7b8c9'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None


def _users_table() -> sa.TableClause:
    return sa.table(
        "users",
        sa.column("id", sa.Uuid()),
        sa.column("organization_id", sa.Uuid()),
        sa.column("role", sa.String()),
    )


def _memberships_table() -> sa.TableClause:
    return sa.table(
        "user_organization_memberships",
        sa.column("id", sa.Uuid()),
        sa.column("user_id", sa.Uuid()),
        sa.column("organization_id", sa.Uuid()),
        sa.column("role", sa.String()),
    )


def upgrade() -> None:
    conn = op.get_bind()
    users = _users_table()
    memberships = _memberships_table()

    # Preserve legacy org associations: every user whose only link to an org
    # is the soon-to-be-dropped column gets a membership row with their
    # legacy role copied over.
    existing = {
        (row.user_id, row.organization_id)
        for row in conn.execute(
            sa.select(memberships.c.user_id, memberships.c.organization_id)
        )
    }
    legacy_rows = conn.execute(
        sa.select(users.c.id, users.c.organization_id, users.c.role).where(
            users.c.organization_id.is_not(None)
        )
    ).fetchall()
    to_insert = [
        {
            "id": uuid.uuid4(),
            "user_id": row.id,
            "organization_id": row.organization_id,
            "role": row.role,
        }
        for row in legacy_rows
        if (row.id, row.organization_id) not in existing
    ]
    if to_insert:
        conn.execute(memberships.insert(), to_insert)

    # Batch mode so the drop also works on SQLite (dev default), where an
    # indexed / FK-bearing column cannot be dropped in place.
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_index(op.f("ix_users_organization_id"))
        batch_op.drop_column("organization_id")


def downgrade() -> None:
    conn = op.get_bind()

    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(
            sa.Column("organization_id", sa.Uuid(), nullable=True)
        )
        batch_op.create_foreign_key(
            "users_organization_id_fkey",
            "organizations",
            ["organization_id"],
            ["id"],
        )
        batch_op.create_index(
            op.f("ix_users_organization_id"), ["organization_id"], unique=False
        )

    # Best-effort restore: users with exactly one membership get that org
    # back; multi-org users cannot be represented by the single-org column
    # and stay NULL.
    memberships = _memberships_table()
    users = _users_table()
    rows = conn.execute(
        sa.select(memberships.c.user_id, memberships.c.organization_id)
    ).fetchall()
    org_by_user: dict = {}
    for row in rows:
        org_by_user.setdefault(row.user_id, set()).add(row.organization_id)
    for user_id, org_ids in org_by_user.items():
        if len(org_ids) == 1:
            conn.execute(
                users.update()
                .where(users.c.id == user_id)
                .values(organization_id=next(iter(org_ids)))
            )
