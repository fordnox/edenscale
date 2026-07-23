"""add audit log country and user_agent

Revision ID: 9c4d1ba6e017
Revises: 2fc15dadfdd0
Create Date: 2026-07-23 17:35:11.402118

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9c4d1ba6e017'
down_revision = '2fc15dadfdd0'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('audit_logs', sa.Column('country', sa.String(length=2), nullable=True))
    op.add_column('audit_logs', sa.Column('user_agent', sa.String(length=400), nullable=True))


def downgrade():
    op.drop_column('audit_logs', 'user_agent')
    op.drop_column('audit_logs', 'country')
