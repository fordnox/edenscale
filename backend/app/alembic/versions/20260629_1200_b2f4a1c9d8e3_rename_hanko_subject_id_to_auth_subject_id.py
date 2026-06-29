"""rename hanko_subject_id to auth_subject_id

Migrates the external IdP subject column from Hanko to Neon Auth. The column
stores the JWT `sub` claim; only its name changes, not its data, so this is a
pure rename of the column and its unique index.

Revision ID: b2f4a1c9d8e3
Revises: 7a3259f3e3bb
Create Date: 2026-06-29 12:00:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'b2f4a1c9d8e3'
down_revision = '7a3259f3e3bb'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_index('ix_users_hanko_subject_id', table_name='users')
    op.alter_column(
        'users', 'hanko_subject_id', new_column_name='auth_subject_id'
    )
    op.create_index(
        op.f('ix_users_auth_subject_id'),
        'users',
        ['auth_subject_id'],
        unique=True,
    )


def downgrade():
    op.drop_index('ix_users_auth_subject_id', table_name='users')
    op.alter_column(
        'users', 'auth_subject_id', new_column_name='hanko_subject_id'
    )
    op.create_index(
        op.f('ix_users_hanko_subject_id'),
        'users',
        ['hanko_subject_id'],
        unique=True,
    )
