"""drop_dead_password_hash_column

Auth is entirely Hanko (see app/core/auth.py) — no code path has ever read
or written ``users.password_hash``. Confirmed by grepping the whole
codebase (excluding app/alembic) for ``password_hash``: the only hit was
the column declaration itself in app/models/user.py. The column has never
held real data (it defaulted to ``""`` on every row), so the downgrade
below recreates it empty and loses nothing.

Revision ID: 6f03ef2aed6b
Revises: 0a6846b7ba21
Create Date: 2026-07-22 00:21:15.761547

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '6f03ef2aed6b'
down_revision = '0a6846b7ba21'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column('users', 'password_hash')


def downgrade() -> None:
    # Recreated empty (default "") — never held data, see module docstring.
    op.add_column(
        'users',
        sa.Column(
            'password_hash', sa.VARCHAR(length=255), nullable=False, server_default=""
        ),
    )
