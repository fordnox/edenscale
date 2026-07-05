"""add_bank_statement_imports

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-07-05 10:00:00.000000

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = 'e5f6a7b8c9d0'
down_revision = 'd4e5f6a7b8c9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bank_statement_imports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("storage_url", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "applied",
                "discarded",
                name="bank_statement_import_status",
            ),
            nullable=False,
        ),
        sa.Column("transaction_count", sa.Integer(), nullable=False),
        sa.Column("applied_count", sa.Integer(), nullable=False),
        sa.Column("imported_by_user_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=True
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["imported_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_bank_statement_imports_organization_id",
        "bank_statement_imports",
        ["organization_id"],
    )
    op.create_index(
        "ix_bank_statement_imports_imported_by_user_id",
        "bank_statement_imports",
        ["imported_by_user_id"],
    )

    op.create_table(
        "bank_payment_transactions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("import_id", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("value_date", sa.Date(), nullable=True),
        sa.Column("debtor_name", sa.String(length=255), nullable=True),
        sa.Column("debtor_iban", sa.String(length=50), nullable=True),
        sa.Column("remittance_info", sa.Text(), nullable=True),
        sa.Column("bank_reference", sa.String(length=255), nullable=False),
        sa.Column("capital_call_item_id", sa.Uuid(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "unmatched",
                "matched",
                "applied",
                "ignored",
                name="bank_payment_transaction_status",
            ),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.func.now(), nullable=True
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=True
        ),
        sa.ForeignKeyConstraint(["import_id"], ["bank_statement_imports.id"]),
        sa.ForeignKeyConstraint(
            ["capital_call_item_id"], ["capital_call_items.id"]
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "import_id",
            "bank_reference",
            name="uq_bank_payment_txn_import_reference",
        ),
    )
    op.create_index(
        "ix_bank_payment_transactions_import_id",
        "bank_payment_transactions",
        ["import_id"],
    )
    op.create_index(
        "ix_bank_payment_transactions_capital_call_item_id",
        "bank_payment_transactions",
        ["capital_call_item_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_bank_payment_transactions_capital_call_item_id",
        table_name="bank_payment_transactions",
    )
    op.drop_index(
        "ix_bank_payment_transactions_import_id",
        table_name="bank_payment_transactions",
    )
    op.drop_table("bank_payment_transactions")
    op.drop_index(
        "ix_bank_statement_imports_imported_by_user_id",
        table_name="bank_statement_imports",
    )
    op.drop_index(
        "ix_bank_statement_imports_organization_id",
        table_name="bank_statement_imports",
    )
    op.drop_table("bank_statement_imports")
    sa.Enum(name="bank_payment_transaction_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="bank_statement_import_status").drop(op.get_bind(), checkfirst=True)
