"""add user_organization_memberships and superadmin role

Revision ID: ee0cff22bcfc
Revises: d496f70bae71
Create Date: 2026-04-30 22:57:15.408554

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ee0cff22bcfc'
down_revision = 'd496f70bae71'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()

    # 1. Add 'superadmin' to the existing user_role enum.
    #    PostgreSQL: ALTER TYPE adds the new value.
    #    SQLite: sa.Enum is rendered as a plain VARCHAR with no CHECK constraint
    #    (SQLAlchemy 2.x default), so nothing schema-level needs to change.
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'superadmin'")

    # 2. Create the user_organization_memberships table (and the membership_role
    #    enum type, implicitly, on PostgreSQL).
    op.create_table(
        'user_organization_memberships',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column(
            'role',
            sa.Enum('superadmin', 'admin', 'fund_manager', 'lp', name='membership_role'),
            nullable=False,
        ),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'organization_id', name='uq_user_org_membership'),
    )
    op.create_index(
        op.f('ix_user_organization_memberships_organization_id'),
        'user_organization_memberships',
        ['organization_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_user_organization_memberships_user_id'),
        'user_organization_memberships',
        ['user_id'],
        unique=False,
    )

    # 3. Backfill: every user with a non-null organization_id gets a membership row,
    #    with role copied from users.role. Idempotent: skipped if no matching users.
    op.execute(
        "INSERT INTO user_organization_memberships "
        "(user_id, organization_id, role, created_at, updated_at) "
        "SELECT id, organization_id, role, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP "
        "FROM users "
        "WHERE organization_id IS NOT NULL"
    )


def downgrade():
    op.drop_index(
        op.f('ix_user_organization_memberships_user_id'),
        table_name='user_organization_memberships',
    )
    op.drop_index(
        op.f('ix_user_organization_memberships_organization_id'),
        table_name='user_organization_memberships',
    )
    op.drop_table('user_organization_memberships')

    # Drop the membership_role enum type on PostgreSQL so a re-upgrade can recreate it.
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS membership_role")

    # NOTE: we deliberately do NOT remove 'superadmin' from the user_role enum on
    # PostgreSQL. Removing an enum value is a one-way door (it requires recreating
    # the type and rewriting any dependent rows), so the value stays in place.
