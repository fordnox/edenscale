"""add organization invitations

Revision ID: 7a3259f3e3bb
Revises: ee0cff22bcfc
Create Date: 2026-05-01 05:09:48.988501

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7a3259f3e3bb'
down_revision = 'ee0cff22bcfc'
branch_labels = None
depends_on = None


def upgrade():
    # Create the organization_invitations table. On PostgreSQL the two
    # sa.Enum columns implicitly create CREATE TYPE statements for
    # 'invitation_role' and 'invitation_status'; on SQLite they are
    # rendered as plain VARCHARs.
    op.create_table(
        'organization_invitations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column(
            'role',
            sa.Enum('superadmin', 'admin', 'fund_manager', 'lp', name='invitation_role'),
            nullable=False,
        ),
        sa.Column('token', sa.String(length=128), nullable=False),
        sa.Column(
            'status',
            sa.Enum('pending', 'accepted', 'revoked', 'expired', name='invitation_status'),
            nullable=False,
        ),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('invited_by_user_id', sa.Integer(), nullable=True),
        sa.Column('accepted_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.ForeignKeyConstraint(['invited_by_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_organization_invitations_email'),
        'organization_invitations',
        ['email'],
        unique=False,
    )
    op.create_index(
        op.f('ix_organization_invitations_invited_by_user_id'),
        'organization_invitations',
        ['invited_by_user_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_organization_invitations_organization_id'),
        'organization_invitations',
        ['organization_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_organization_invitations_token'),
        'organization_invitations',
        ['token'],
        unique=True,
    )


def downgrade():
    op.drop_index(
        op.f('ix_organization_invitations_token'),
        table_name='organization_invitations',
    )
    op.drop_index(
        op.f('ix_organization_invitations_organization_id'),
        table_name='organization_invitations',
    )
    op.drop_index(
        op.f('ix_organization_invitations_invited_by_user_id'),
        table_name='organization_invitations',
    )
    op.drop_index(
        op.f('ix_organization_invitations_email'),
        table_name='organization_invitations',
    )
    op.drop_table('organization_invitations')

    # Drop the implicitly-created enum types on PostgreSQL so a re-upgrade
    # can recreate them. SQLite renders sa.Enum as VARCHAR with no type to
    # drop, so this is a no-op there.
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS invitation_status")
        op.execute("DROP TYPE IF EXISTS invitation_role")
