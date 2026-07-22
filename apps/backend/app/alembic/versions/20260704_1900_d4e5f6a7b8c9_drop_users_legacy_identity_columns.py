"""drop_users_legacy_identity_columns

Memberships (user_organization_memberships) are the source of truth for who
belongs to an organization and with what role, and superadmins are defined
purely by the SUPERADMIN_EMAIL setting — so both legacy identity columns on
``users`` go away:

* ``organization_id`` — backfill any membership rows still missing from
  legacy data (copying the legacy role), then drop.
* ``role`` — global roles no longer exist; drop (former superadmins must be
  listed in SUPERADMIN_EMAIL to keep their access).

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-07-04 19:00:00.000000

"""

import uuid

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
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
            # Memberships never carry the superadmin role; superadmins are
            # config-defined and act on orgs via synthesized memberships.
            "role": row.role if row.role != "superadmin" else "admin",
        }
        for row in legacy_rows
        if (row.id, row.organization_id) not in existing
    ]
    if to_insert:
        conn.execute(memberships.insert(), to_insert)

    # Batch mode so the drops also work on SQLite (dev default), where an
    # indexed / FK-bearing column cannot be dropped in place.
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_index(op.f("ix_users_organization_id"))
        batch_op.drop_column("organization_id")
        batch_op.drop_column("role")

    # The user_role enum type has no remaining columns on Postgres.
    if conn.dialect.name == "postgresql":
        sa.Enum(name="user_role").drop(conn, checkfirst=True)


def downgrade() -> None:
    conn = op.get_bind()

    role_enum = sa.Enum("superadmin", "admin", "fund_manager", "lp", name="user_role")
    role_enum.create(conn, checkfirst=True)

    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(
            sa.Column("role", role_enum, nullable=False, server_default="lp")
        )
        batch_op.add_column(sa.Column("organization_id", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            "users_organization_id_fkey",
            "organizations",
            ["organization_id"],
            ["id"],
        )
        batch_op.create_index(
            op.f("ix_users_organization_id"), ["organization_id"], unique=False
        )

    # Best-effort restore: users with exactly one membership get that org and
    # role back; multi-org users cannot be represented by the single-org
    # columns and keep the defaults.
    memberships = _memberships_table()
    users = _users_table()
    rows = conn.execute(
        sa.select(
            memberships.c.user_id,
            memberships.c.organization_id,
            memberships.c.role,
        )
    ).fetchall()
    by_user: dict = {}
    for row in rows:
        by_user.setdefault(row.user_id, []).append(row)
    for user_id, user_rows in by_user.items():
        if len(user_rows) == 1:
            conn.execute(
                users.update()
                .where(users.c.id == user_id)
                .values(
                    organization_id=user_rows[0].organization_id,
                    role=user_rows[0].role,
                )
            )
