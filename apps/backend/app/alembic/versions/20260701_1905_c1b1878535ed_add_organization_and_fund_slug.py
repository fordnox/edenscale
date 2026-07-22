"""add_organization_and_fund_slug

Revision ID: c1b1878535ed
Revises: 6010fd6f02bf
Create Date: 2026-07-01 19:05:30.933703

"""

import re

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c1b1878535ed"
down_revision = "6010fd6f02bf"
branch_labels = None
depends_on = None

# Deliberately duplicated (not imported from app.core.slugs) so this
# migration keeps producing the same output regardless of future changes
# to the application-level slug helper.
_NON_SLUG_CHARS = re.compile(r"[^a-z0-9-]+")
_REPEATED_HYPHENS = re.compile(r"-{2,}")
_RESERVED_SLUGS = frozenset(
    {
        "app",
        "login",
        "profile",
        "onboarding",
        "settings",
        "superadmin",
        "invitations",
        "api",
        "funds",
        "investors",
        "calls",
        "distributions",
        "documents",
        "letters",
        "tasks",
        "notifications",
        "audit-log",
    }
)


def _slugify(value: str) -> str:
    candidate = (value or "").strip().lower().replace(" ", "-")
    candidate = _NON_SLUG_CHARS.sub("-", candidate)
    candidate = _REPEATED_HYPHENS.sub("-", candidate).strip("-")
    candidate = candidate[:80].strip("-")
    return candidate or "org"


def _backfill_slugs(bind, table, *, scope_column=None):
    """Assign a deterministic, unique slug to every row of ``table``.

    Ordered by (created_at, id) so re-running this migration against a
    differently-ordered dataset would still be internally consistent.
    Uniqueness is scoped per ``scope_column`` value when given (funds are
    unique per organization_id), otherwise global (organizations).
    """
    rows = bind.execute(
        sa.text(
            f"SELECT id, name{', ' + scope_column if scope_column else ''} "
            f"FROM {table} ORDER BY created_at, id"
        )
    ).fetchall()

    used: dict[object, set[str]] = {}
    for row in rows:
        scope_key = row[2] if scope_column else None
        seen = used.setdefault(scope_key, set())
        root = _slugify(row[1])
        candidate = root
        suffix = 2
        while candidate in seen or candidate in _RESERVED_SLUGS:
            candidate = f"{root}-{suffix}"
            suffix += 1
        seen.add(candidate)
        bind.execute(
            sa.text(f"UPDATE {table} SET slug = :slug WHERE id = :id"),
            {"slug": candidate, "id": row[0]},
        )


def upgrade():
    bind = op.get_bind()

    op.add_column(
        "organizations", sa.Column("slug", sa.String(length=255), nullable=True)
    )
    op.add_column("funds", sa.Column("slug", sa.String(length=255), nullable=True))

    _backfill_slugs(bind, "organizations")
    _backfill_slugs(bind, "funds", scope_column="organization_id")

    # batch_alter_table so ALTER-of-constraint operations also work on the
    # SQLite dev database (which rebuilds the table instead).
    with op.batch_alter_table("organizations") as batch_op:
        batch_op.alter_column(
            "slug", existing_type=sa.String(length=255), nullable=False
        )
    with op.batch_alter_table("funds") as batch_op:
        batch_op.alter_column(
            "slug", existing_type=sa.String(length=255), nullable=False
        )
        batch_op.create_unique_constraint(
            "uq_funds_organization_id_slug", ["organization_id", "slug"]
        )

    op.create_index(
        op.f("ix_organizations_slug"), "organizations", ["slug"], unique=True
    )
    op.create_index(op.f("ix_funds_slug"), "funds", ["slug"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_funds_slug"), table_name="funds")
    with op.batch_alter_table("funds") as batch_op:
        batch_op.drop_constraint("uq_funds_organization_id_slug", type_="unique")
        batch_op.drop_column("slug")
    op.drop_index(op.f("ix_organizations_slug"), table_name="organizations")
    op.drop_column("organizations", "slug")
