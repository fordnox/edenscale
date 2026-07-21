import uuid
from dataclasses import dataclass
from datetime import datetime, time, timezone
from decimal import Decimal

from sqlalchemy.orm import Session, selectinload

from app.models.bank_payment_transaction import BankPaymentTransaction
from app.models.bank_statement_import import BankStatementImport
from app.models.capital_call import CapitalCall
from app.models.capital_call_item import CapitalCallItem
from app.models.enums import (
    BankPaymentTransactionStatus,
    BankStatementImportStatus,
)
from app.models.fund import Fund
from app.repositories.capital_call_repository import CapitalCallRepository
from app.schemas.bank_import import ApplyAssignment
from app.services.iso20022 import ParsedBankEntry


@dataclass
class _ResolvedPayment:
    """A validated assignment, ready to be written in phase 2 of ``apply``."""

    txn: BankPaymentTransaction
    item: CapitalCallItem
    new_amount_paid: Decimal
    paid_at: datetime


class BankImportRepository:
    def __init__(self, db: Session):
        self.db = db
        self._capital_calls = CapitalCallRepository(db)

    def create_import(
        self,
        *,
        organization_id: uuid.UUID,
        file_name: str,
        storage_url: str | None,
        entries: list[ParsedBankEntry],
        imported_by_user_id: uuid.UUID | None,
    ) -> BankStatementImport:
        """Persist an import batch and one transaction per parsed credit.

        Duplicate ``bank_reference`` values inside a single file are collapsed —
        the unique constraint would reject them anyway, and a statement should
        never list the same transaction twice.
        """
        record = BankStatementImport(
            organization_id=organization_id,
            file_name=file_name,
            storage_url=storage_url,
            status=BankStatementImportStatus.pending,
            imported_by_user_id=imported_by_user_id,
        )
        self.db.add(record)
        self.db.flush()

        seen: set[str] = set()
        transactions: list[BankPaymentTransaction] = []
        for entry in entries:
            if entry.bank_reference in seen:
                continue
            seen.add(entry.bank_reference)
            transactions.append(
                BankPaymentTransaction(
                    import_id=record.id,
                    amount=entry.amount,
                    currency=entry.currency or None,
                    value_date=entry.value_date,
                    debtor_name=entry.debtor_name,
                    debtor_iban=entry.debtor_iban,
                    remittance_info=entry.remittance_info,
                    bank_reference=entry.bank_reference,
                    status=BankPaymentTransactionStatus.unmatched,
                )
            )
        self.db.add_all(transactions)
        record.transaction_count = len(transactions)
        self.db.commit()
        self.db.refresh(record)
        return record

    def get(self, import_id: uuid.UUID) -> BankStatementImport | None:
        return (
            self.db.query(BankStatementImport)
            .options(selectinload(BankStatementImport.transactions))
            .filter(BankStatementImport.id == import_id)
            .first()
        )

    def list_for_org(
        self,
        organization_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> list[BankStatementImport]:
        return (
            self.db.query(BankStatementImport)
            .filter(BankStatementImport.organization_id == organization_id)
            .order_by(
                BankStatementImport.created_at.desc(), BankStatementImport.id.desc()
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def _item_in_org(
        self, capital_call_item_id: uuid.UUID, organization_id: uuid.UUID
    ) -> CapitalCallItem | None:
        return (
            self.db.query(CapitalCallItem)
            .join(CapitalCall, CapitalCall.id == CapitalCallItem.capital_call_id)
            .join(Fund, Fund.id == CapitalCall.fund_id)
            .filter(
                CapitalCallItem.id == capital_call_item_id,
                Fund.organization_id == organization_id,
            )
            .first()
        )

    def _reference_already_applied(
        self,
        *,
        bank_reference: str,
        organization_id: uuid.UUID,
        exclude_txn_id: uuid.UUID,
    ) -> bool:
        """True if this bank reference was already applied elsewhere in the org.

        Guards against a re-uploaded statement double-paying: even in a fresh
        import batch, a transaction whose reference already settled an item is
        skipped.
        """
        return (
            self.db.query(BankPaymentTransaction.id)
            .join(
                BankStatementImport,
                BankStatementImport.id == BankPaymentTransaction.import_id,
            )
            .filter(
                BankPaymentTransaction.bank_reference == bank_reference,
                BankPaymentTransaction.status == BankPaymentTransactionStatus.applied,
                BankPaymentTransaction.id != exclude_txn_id,
                BankStatementImport.organization_id == organization_id,
            )
            .first()
            is not None
        )

    def apply(
        self,
        record: BankStatementImport,
        *,
        assignments: list[ApplyAssignment],
        ignore_transaction_ids: list[uuid.UUID],
    ) -> BankStatementImport:
        """Write confirmed payments onto capital-call items. Idempotent.

        Each assignment *adds* its amount to the item's existing ``amount_paid``
        (via ``CapitalCallRepository.set_item_payment``, which recomputes the
        call status). Transactions already applied — here or in another import
        with the same reference — are skipped.

        Validation runs in a read-only phase before any write, so that a bad
        assignment raises before anything is mutated: a 400 from this call
        must leave the database exactly as it was, and a retry after that 400
        must not re-apply what already landed. See plans/003-atomic-bank-apply.md.
        """
        organization_id = record.organization_id
        by_id = {txn.id: txn for txn in record.transactions}

        # Phase 1 — resolve and validate every assignment. No writes here:
        # raising partway through must leave the database untouched. Track
        # running per-item totals locally (rather than mutating `item`) so
        # that two assignments in the same call targeting the same item still
        # stack correctly, matching the pre-fix sequential-mutation behavior.
        running_totals: dict[uuid.UUID, Decimal] = {}
        to_ignore: list[BankPaymentTransaction] = []
        to_apply: list[_ResolvedPayment] = []
        for assignment in assignments:
            txn = by_id.get(assignment.transaction_id)
            if txn is None:
                raise ValueError(
                    f"Transaction {assignment.transaction_id} is not part of this import"
                )
            if txn.status == BankPaymentTransactionStatus.applied:
                continue  # idempotent re-apply
            if self._reference_already_applied(
                bank_reference=txn.bank_reference,
                organization_id=organization_id,  # type: ignore[invalid-argument-type]
                exclude_txn_id=txn.id,
            ):
                to_ignore.append(txn)
                continue
            item = self._item_in_org(
                assignment.capital_call_item_id,
                organization_id,  # type: ignore[invalid-argument-type]
            )
            if item is None:
                raise ValueError(
                    f"Capital call item {assignment.capital_call_item_id} "
                    "not found in this organization"
                )
            current_amount_paid = running_totals.get(  # type: ignore[no-matching-overload]
                item.id, Decimal(item.amount_paid)  # type: ignore[invalid-argument-type]
            )
            new_amount_paid = current_amount_paid + assignment.amount
            running_totals[item.id] = new_amount_paid  # type: ignore[invalid-argument-type]
            paid_at = (
                datetime.combine(txn.value_date, time.min)
                if txn.value_date is not None
                # Naive-UTC to match the timezone-less DateTime column, per
                # the convention documented at user_repository.py:180-183.
                else datetime.now(timezone.utc).replace(tzinfo=None)
            )
            to_apply.append(
                _ResolvedPayment(
                    txn=txn, item=item, new_amount_paid=new_amount_paid, paid_at=paid_at
                )
            )

        # Phase 2 — write. Only reached once phase 1 has validated every
        # assignment without raising.
        for txn in to_ignore:
            txn.status = BankPaymentTransactionStatus.ignored
        for resolved in to_apply:
            self._capital_calls.set_item_payment(
                resolved.item.id,
                resolved.new_amount_paid,
                resolved.paid_at,
                commit=False,
            )
            resolved.txn.capital_call_item_id = resolved.item.id
            resolved.txn.status = BankPaymentTransactionStatus.applied

        ignore_set = set(ignore_transaction_ids)
        for txn in record.transactions:
            if (
                txn.id in ignore_set
                and txn.status != BankPaymentTransactionStatus.applied
            ):
                txn.status = BankPaymentTransactionStatus.ignored

        applied = [
            txn
            for txn in record.transactions
            if txn.status == BankPaymentTransactionStatus.applied
        ]
        record.applied_count = len(applied)
        if applied:
            record.status = BankStatementImportStatus.applied
        self.db.commit()
        self.db.refresh(record)
        return record
