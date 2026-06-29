"""initial schema from dbml

Revision ID: d496f70bae71
Revises: 3c9336ee4c60
Create Date: 2026-04-29 23:10:06.674306

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd496f70bae71'
down_revision = '3c9336ee4c60'
branch_labels = None
depends_on = None


def upgrade():
    # The prior migration (3c9336ee4c60) created a Hanko-shaped `users` table
    # (id VARCHAR(36), email, name, picture). The dbml schema redefines `users`
    # with an Integer PK and a different column set. Drop and recreate rather
    # than altering, since SQLite cannot ALTER a column type and many of the new
    # NOT NULL columns have no sensible server default for backfill.
    op.drop_index(op.f('ix_users_id'), table_name='users')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')

    op.create_table(
        'organizations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('type', sa.Enum('fund_manager_firm', 'investor_firm', 'service_provider', name='organization_type'), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('legal_name', sa.String(length=255), nullable=True),
        sa.Column('tax_id', sa.String(length=100), nullable=True),
        sa.Column('website', sa.String(length=255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.Column('role', sa.Enum('admin', 'fund_manager', 'lp', name='user_role'), nullable=False),
        sa.Column('first_name', sa.String(length=100), nullable=False),
        sa.Column('last_name', sa.String(length=100), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('phone', sa.String(length=50), nullable=True),
        sa.Column('title', sa.String(length=150), nullable=True),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('last_login_at', sa.DateTime(), nullable=True),
        sa.Column('hanko_subject_id', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_hanko_subject_id'), 'users', ['hanko_subject_id'], unique=True)
    op.create_index(op.f('ix_users_organization_id'), 'users', ['organization_id'], unique=False)

    op.create_table(
        'investors',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('investor_code', sa.String(length=50), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('investor_type', sa.String(length=100), nullable=True),
        sa.Column('accredited', sa.Boolean(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('investor_code'),
    )
    op.create_index(op.f('ix_investors_organization_id'), 'investors', ['organization_id'], unique=False)

    op.create_table(
        'audit_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.Column('action', sa.String(length=150), nullable=False),
        sa.Column('entity_type', sa.String(length=100), nullable=True),
        sa.Column('entity_id', sa.Integer(), nullable=True),
        sa.Column('metadata', sa.Text(), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_audit_logs_organization_id'), 'audit_logs', ['organization_id'], unique=False)
    op.create_index(op.f('ix_audit_logs_user_id'), 'audit_logs', ['user_id'], unique=False)

    op.create_table(
        'fund_groups',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_fund_groups_created_by_user_id'), 'fund_groups', ['created_by_user_id'], unique=False)
    op.create_index(op.f('ix_fund_groups_organization_id'), 'fund_groups', ['organization_id'], unique=False)

    op.create_table(
        'investor_contacts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('investor_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('first_name', sa.String(length=100), nullable=False),
        sa.Column('last_name', sa.String(length=100), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('phone', sa.String(length=50), nullable=True),
        sa.Column('title', sa.String(length=150), nullable=True),
        sa.Column('is_primary', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.ForeignKeyConstraint(['investor_id'], ['investors.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_investor_contacts_investor_id'), 'investor_contacts', ['investor_id'], unique=False)
    op.create_index(op.f('ix_investor_contacts_user_id'), 'investor_contacts', ['user_id'], unique=False)

    op.create_table(
        'notifications',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('status', sa.Enum('unread', 'read', 'archived', name='notification_status'), nullable=False),
        sa.Column('related_type', sa.String(length=100), nullable=True),
        sa.Column('related_id', sa.Integer(), nullable=True),
        sa.Column('read_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_notifications_user_id'), 'notifications', ['user_id'], unique=False)

    op.create_table(
        'funds',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('fund_group_id', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('legal_name', sa.String(length=255), nullable=True),
        sa.Column('vintage_year', sa.Integer(), nullable=True),
        sa.Column('strategy', sa.String(length=255), nullable=True),
        sa.Column('currency_code', sa.String(length=3), nullable=False),
        sa.Column('target_size', sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column('hard_cap', sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column('current_size', sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column('status', sa.Enum('draft', 'active', 'closed', 'liquidating', 'archived', name='fund_status'), nullable=False),
        sa.Column('inception_date', sa.Date(), nullable=True),
        sa.Column('close_date', sa.Date(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.ForeignKeyConstraint(['fund_group_id'], ['fund_groups.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_funds_fund_group_id'), 'funds', ['fund_group_id'], unique=False)
    op.create_index(op.f('ix_funds_organization_id'), 'funds', ['organization_id'], unique=False)

    op.create_table(
        'capital_calls',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('fund_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('due_date', sa.Date(), nullable=False),
        sa.Column('call_date', sa.Date(), nullable=True),
        sa.Column('amount', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('status', sa.Enum('draft', 'scheduled', 'sent', 'partially_paid', 'paid', 'overdue', 'cancelled', name='capital_call_status'), nullable=False),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['fund_id'], ['funds.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_capital_calls_created_by_user_id'), 'capital_calls', ['created_by_user_id'], unique=False)
    op.create_index(op.f('ix_capital_calls_fund_id'), 'capital_calls', ['fund_id'], unique=False)

    op.create_table(
        'commitments',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('fund_id', sa.Integer(), nullable=False),
        sa.Column('investor_id', sa.Integer(), nullable=False),
        sa.Column('committed_amount', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('called_amount', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('distributed_amount', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('commitment_date', sa.Date(), nullable=False),
        sa.Column('status', sa.Enum('pending', 'approved', 'declined', 'cancelled', name='commitment_status'), nullable=False),
        sa.Column('share_class', sa.String(length=100), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.ForeignKeyConstraint(['fund_id'], ['funds.id']),
        sa.ForeignKeyConstraint(['investor_id'], ['investors.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('fund_id', 'investor_id', name='uq_commitment_fund_investor'),
    )
    op.create_index(op.f('ix_commitments_fund_id'), 'commitments', ['fund_id'], unique=False)
    op.create_index(op.f('ix_commitments_investor_id'), 'commitments', ['investor_id'], unique=False)

    op.create_table(
        'communications',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('fund_id', sa.Integer(), nullable=True),
        sa.Column('sender_user_id', sa.Integer(), nullable=True),
        sa.Column('type', sa.Enum('announcement', 'message', 'notification', name='communication_type'), nullable=False),
        sa.Column('subject', sa.String(length=255), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.ForeignKeyConstraint(['fund_id'], ['funds.id']),
        sa.ForeignKeyConstraint(['sender_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_communications_fund_id'), 'communications', ['fund_id'], unique=False)
    op.create_index(op.f('ix_communications_sender_user_id'), 'communications', ['sender_user_id'], unique=False)

    op.create_table(
        'distributions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('fund_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('distribution_date', sa.Date(), nullable=False),
        sa.Column('record_date', sa.Date(), nullable=True),
        sa.Column('amount', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('status', sa.Enum('draft', 'scheduled', 'sent', 'partially_paid', 'paid', 'cancelled', name='distribution_status'), nullable=False),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['fund_id'], ['funds.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_distributions_created_by_user_id'), 'distributions', ['created_by_user_id'], unique=False)
    op.create_index(op.f('ix_distributions_fund_id'), 'distributions', ['fund_id'], unique=False)

    op.create_table(
        'documents',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.Column('fund_id', sa.Integer(), nullable=True),
        sa.Column('investor_id', sa.Integer(), nullable=True),
        sa.Column('uploaded_by_user_id', sa.Integer(), nullable=True),
        sa.Column('document_type', sa.Enum('legal', 'kyc_aml', 'financial', 'report', 'notice', 'other', name='document_type'), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('file_name', sa.String(length=255), nullable=False),
        sa.Column('file_url', sa.Text(), nullable=False),
        sa.Column('mime_type', sa.String(length=100), nullable=True),
        sa.Column('file_size', sa.BigInteger(), nullable=True),
        sa.Column('is_confidential', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.ForeignKeyConstraint(['fund_id'], ['funds.id']),
        sa.ForeignKeyConstraint(['investor_id'], ['investors.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['uploaded_by_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_documents_fund_id'), 'documents', ['fund_id'], unique=False)
    op.create_index(op.f('ix_documents_investor_id'), 'documents', ['investor_id'], unique=False)
    op.create_index(op.f('ix_documents_organization_id'), 'documents', ['organization_id'], unique=False)
    op.create_index(op.f('ix_documents_uploaded_by_user_id'), 'documents', ['uploaded_by_user_id'], unique=False)

    op.create_table(
        'fund_team_members',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('fund_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=150), nullable=True),
        sa.Column('permissions', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.ForeignKeyConstraint(['fund_id'], ['funds.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('fund_id', 'user_id', name='uq_fund_team_member_fund_user'),
    )
    op.create_index(op.f('ix_fund_team_members_fund_id'), 'fund_team_members', ['fund_id'], unique=False)
    op.create_index(op.f('ix_fund_team_members_user_id'), 'fund_team_members', ['user_id'], unique=False)

    op.create_table(
        'tasks',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('fund_id', sa.Integer(), nullable=True),
        sa.Column('assigned_to_user_id', sa.Integer(), nullable=True),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.Enum('open', 'in_progress', 'done', 'cancelled', name='task_status'), nullable=False),
        sa.Column('due_date', sa.Date(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.ForeignKeyConstraint(['assigned_to_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['fund_id'], ['funds.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_tasks_assigned_to_user_id'), 'tasks', ['assigned_to_user_id'], unique=False)
    op.create_index(op.f('ix_tasks_created_by_user_id'), 'tasks', ['created_by_user_id'], unique=False)
    op.create_index(op.f('ix_tasks_fund_id'), 'tasks', ['fund_id'], unique=False)

    op.create_table(
        'capital_call_items',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('capital_call_id', sa.Integer(), nullable=False),
        sa.Column('commitment_id', sa.Integer(), nullable=False),
        sa.Column('amount_due', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('amount_paid', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('paid_at', sa.DateTime(), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.ForeignKeyConstraint(['capital_call_id'], ['capital_calls.id']),
        sa.ForeignKeyConstraint(['commitment_id'], ['commitments.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('capital_call_id', 'commitment_id', name='uq_capital_call_item_call_commitment'),
    )
    op.create_index(op.f('ix_capital_call_items_capital_call_id'), 'capital_call_items', ['capital_call_id'], unique=False)
    op.create_index(op.f('ix_capital_call_items_commitment_id'), 'capital_call_items', ['commitment_id'], unique=False)

    op.create_table(
        'communication_recipients',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('communication_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('investor_contact_id', sa.Integer(), nullable=True),
        sa.Column('delivered_at', sa.DateTime(), nullable=True),
        sa.Column('read_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.ForeignKeyConstraint(['communication_id'], ['communications.id']),
        sa.ForeignKeyConstraint(['investor_contact_id'], ['investor_contacts.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('communication_id', 'user_id', name='uq_communication_recipient_comm_user'),
    )
    op.create_index(op.f('ix_communication_recipients_communication_id'), 'communication_recipients', ['communication_id'], unique=False)
    op.create_index(op.f('ix_communication_recipients_investor_contact_id'), 'communication_recipients', ['investor_contact_id'], unique=False)
    op.create_index(op.f('ix_communication_recipients_user_id'), 'communication_recipients', ['user_id'], unique=False)

    op.create_table(
        'distribution_items',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('distribution_id', sa.Integer(), nullable=False),
        sa.Column('commitment_id', sa.Integer(), nullable=False),
        sa.Column('amount_due', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('amount_paid', sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column('paid_at', sa.DateTime(), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.ForeignKeyConstraint(['commitment_id'], ['commitments.id']),
        sa.ForeignKeyConstraint(['distribution_id'], ['distributions.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('distribution_id', 'commitment_id', name='uq_distribution_item_dist_commitment'),
    )
    op.create_index(op.f('ix_distribution_items_commitment_id'), 'distribution_items', ['commitment_id'], unique=False)
    op.create_index(op.f('ix_distribution_items_distribution_id'), 'distribution_items', ['distribution_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_distribution_items_distribution_id'), table_name='distribution_items')
    op.drop_index(op.f('ix_distribution_items_commitment_id'), table_name='distribution_items')
    op.drop_table('distribution_items')
    op.drop_index(op.f('ix_communication_recipients_user_id'), table_name='communication_recipients')
    op.drop_index(op.f('ix_communication_recipients_investor_contact_id'), table_name='communication_recipients')
    op.drop_index(op.f('ix_communication_recipients_communication_id'), table_name='communication_recipients')
    op.drop_table('communication_recipients')
    op.drop_index(op.f('ix_capital_call_items_commitment_id'), table_name='capital_call_items')
    op.drop_index(op.f('ix_capital_call_items_capital_call_id'), table_name='capital_call_items')
    op.drop_table('capital_call_items')
    op.drop_index(op.f('ix_tasks_fund_id'), table_name='tasks')
    op.drop_index(op.f('ix_tasks_created_by_user_id'), table_name='tasks')
    op.drop_index(op.f('ix_tasks_assigned_to_user_id'), table_name='tasks')
    op.drop_table('tasks')
    op.drop_index(op.f('ix_fund_team_members_user_id'), table_name='fund_team_members')
    op.drop_index(op.f('ix_fund_team_members_fund_id'), table_name='fund_team_members')
    op.drop_table('fund_team_members')
    op.drop_index(op.f('ix_documents_uploaded_by_user_id'), table_name='documents')
    op.drop_index(op.f('ix_documents_organization_id'), table_name='documents')
    op.drop_index(op.f('ix_documents_investor_id'), table_name='documents')
    op.drop_index(op.f('ix_documents_fund_id'), table_name='documents')
    op.drop_table('documents')
    op.drop_index(op.f('ix_distributions_fund_id'), table_name='distributions')
    op.drop_index(op.f('ix_distributions_created_by_user_id'), table_name='distributions')
    op.drop_table('distributions')
    op.drop_index(op.f('ix_communications_sender_user_id'), table_name='communications')
    op.drop_index(op.f('ix_communications_fund_id'), table_name='communications')
    op.drop_table('communications')
    op.drop_index(op.f('ix_commitments_investor_id'), table_name='commitments')
    op.drop_index(op.f('ix_commitments_fund_id'), table_name='commitments')
    op.drop_table('commitments')
    op.drop_index(op.f('ix_capital_calls_fund_id'), table_name='capital_calls')
    op.drop_index(op.f('ix_capital_calls_created_by_user_id'), table_name='capital_calls')
    op.drop_table('capital_calls')
    op.drop_index(op.f('ix_funds_organization_id'), table_name='funds')
    op.drop_index(op.f('ix_funds_fund_group_id'), table_name='funds')
    op.drop_table('funds')
    op.drop_index(op.f('ix_notifications_user_id'), table_name='notifications')
    op.drop_table('notifications')
    op.drop_index(op.f('ix_investor_contacts_user_id'), table_name='investor_contacts')
    op.drop_index(op.f('ix_investor_contacts_investor_id'), table_name='investor_contacts')
    op.drop_table('investor_contacts')
    op.drop_index(op.f('ix_fund_groups_organization_id'), table_name='fund_groups')
    op.drop_index(op.f('ix_fund_groups_created_by_user_id'), table_name='fund_groups')
    op.drop_table('fund_groups')
    op.drop_index(op.f('ix_audit_logs_user_id'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_organization_id'), table_name='audit_logs')
    op.drop_table('audit_logs')
    op.drop_index(op.f('ix_investors_organization_id'), table_name='investors')
    op.drop_table('investors')
    op.drop_index(op.f('ix_users_organization_id'), table_name='users')
    op.drop_index(op.f('ix_users_hanko_subject_id'), table_name='users')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
    op.drop_table('organizations')

    # Restore the prior Hanko-shaped users table (matches 3c9336ee4c60 upgrade).
    op.create_table(
        'users',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=True),
        sa.Column('picture', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
