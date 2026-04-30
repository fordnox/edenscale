from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Query, Session, joinedload

from app.models.capital_call import CapitalCall
from app.models.capital_call_item import CapitalCallItem
from app.models.commitment import Commitment
from app.models.enums import CapitalCallStatus, UserRole
from app.models.fund import Fund
from app.models.investor_contact import InvestorContact
from app.models.user import User
from app.repositories.commitment_repository import CommitmentRepository
from app.schemas.capital_call import CapitalCallCreate, CapitalCallUpdate

_SENDABLE_STATUSES = {CapitalCallStatus.draft, CapitalCallStatus.scheduled}
_TERMINAL_STATUSES = {CapitalCallStatus.cancelled}
_ALLOWED_TRANSITIONS: dict[CapitalCallStatus, set[CapitalCallStatus]] = {
    CapitalCallStatus.draft: {
        CapitalCallStatus.scheduled,
        CapitalCallStatus.sent,
        CapitalCallStatus.cancelled,
    },
    CapitalCallStatus.scheduled: {
        CapitalCallStatus.sent,
        CapitalCallStatus.cancelled,
    },
    CapitalCallStatus.sent: {
        CapitalCallStatus.partially_paid,
        CapitalCallStatus.paid,
        CapitalCallStatus.overdue,
        CapitalCallStatus.cancelled,
    },
    CapitalCallStatus.partially_paid: {
        CapitalCallStatus.paid,
        CapitalCallStatus.overdue,
        CapitalCallStatus.cancelled,
    },
    CapitalCallStatus.overdue: {
        CapitalCallStatus.partially_paid,
        CapitalCallStatus.paid,
        CapitalCallStatus.cancelled,
    },
    CapitalCallStatus.paid: set(),
    CapitalCallStatus.cancelled: set(),
}


class CapitalCallRepository:
    def __init__(self, db: Session):
        self.db = db
        self._commitments = CommitmentRepository(db)

    def _base_query(self) -> Query:
        return self.db.query(CapitalCall).options(
            joinedload(CapitalCall.items),
            joinedload(CapitalCall.fund),
        )

    def list_for_user(
        self,
        user: User,
        *,
        fund_id: int | None = None,
        status: CapitalCallStatus | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[CapitalCall]:
        query = self._base_query()
        if user.role is UserRole.admin:
            pass
        elif user.role is UserRole.fund_manager:
            if user.organization_id is None:
                return []
            query = query.join(Fund, Fund.id == CapitalCall.fund_id).filter(
                Fund.organization_id == user.organization_id
            )
        else:
            visible_investor_ids = select(InvestorContact.investor_id).where(
                InvestorContact.user_id == user.id
            )
            visible_call_ids = (
                select(CapitalCallItem.capital_call_id)
                .join(
                    Commitment,
                    Commitment.id == CapitalCallItem.commitment_id,
                )
                .where(Commitment.investor_id.in_(visible_investor_ids))
            )
            query = query.filter(CapitalCall.id.in_(visible_call_ids))
        if fund_id is not None:
            query = query.filter(CapitalCall.fund_id == fund_id)
        if status is not None:
            query = query.filter(CapitalCall.status == status)
        return query.order_by(CapitalCall.id).offset(skip).limit(limit).all()

    def get_with_items(self, call_id: int) -> CapitalCall | None:
        return self._base_query().filter(CapitalCall.id == call_id).first()

    def user_can_view(self, user: User, call: CapitalCall) -> bool:
        if user.role is UserRole.admin:
            return True
        if user.role is UserRole.fund_manager:
            fund = self.db.query(Fund).filter(Fund.id == call.fund_id).first()
            if fund is None:
                return False
            return bool(fund.organization_id == user.organization_id)
        return (
            self.db.query(CapitalCallItem.id)
            .join(Commitment, Commitment.id == CapitalCallItem.commitment_id)
            .join(
                InvestorContact,
                InvestorContact.investor_id == Commitment.investor_id,
            )
            .filter(
                CapitalCallItem.capital_call_id == call.id,
                InvestorContact.user_id == user.id,
            )
            .first()
            is not None
        )

    def create_draft(
        self, data: CapitalCallCreate, *, created_by_user_id: int | None = None
    ) -> CapitalCall:
        call = CapitalCall(
            fund_id=data.fund_id,
            title=data.title,
            description=data.description,
            due_date=data.due_date,
            call_date=data.call_date,
            amount=data.amount,
            status=CapitalCallStatus.draft,
            created_by_user_id=created_by_user_id,
        )
        self.db.add(call)
        self.db.commit()
        self.db.refresh(call)
        return call

    def update(self, call_id: int, data: CapitalCallUpdate) -> CapitalCall | None:
        call = self.db.query(CapitalCall).filter(CapitalCall.id == call_id).first()
        if call is None:
            return None
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(call, key, value)
        self.db.commit()
        self.db.refresh(call)
        return self.get_with_items(call_id)

    def add_items(
        self,
        call_id: int,
        allocations: list[tuple[int, Decimal]],
    ) -> list[CapitalCallItem]:
        """Bulk-insert allocations on the capital call.

        `allocations` is a list of `(commitment_id, amount_due)` tuples.
        Rejects entries whose commitment belongs to a different fund or that
        duplicate an existing allocation for the call.
        """
        call = self.db.query(CapitalCall).filter(CapitalCall.id == call_id).first()
        if call is None:
            raise ValueError("Capital call not found")
        if not allocations:
            return []
        commitment_ids = [c_id for c_id, _ in allocations]
        commitments = (
            self.db.query(Commitment).filter(Commitment.id.in_(commitment_ids)).all()
        )
        commitments_by_id = {c.id: c for c in commitments}
        for commitment_id, _ in allocations:
            commitment = commitments_by_id.get(commitment_id)
            if commitment is None:
                raise ValueError(f"Commitment {commitment_id} not found")
            if commitment.fund_id != call.fund_id:
                raise ValueError(
                    f"Commitment {commitment_id} does not belong to fund {call.fund_id}"
                )
        existing = (
            self.db.query(CapitalCallItem.commitment_id)
            .filter(CapitalCallItem.capital_call_id == call_id)
            .all()
        )
        existing_ids = {row[0] for row in existing}
        for commitment_id, _ in allocations:
            if commitment_id in existing_ids:
                raise ValueError(
                    f"Allocation for commitment {commitment_id} already exists"
                )
        items = [
            CapitalCallItem(
                capital_call_id=call_id,
                commitment_id=commitment_id,
                amount_due=amount_due,
            )
            for commitment_id, amount_due in allocations
        ]
        self.db.add_all(items)
        self.db.flush()
        for commitment_id, _ in allocations:
            self._commitments.recompute_totals(commitment_id)
        self.db.commit()
        for item in items:
            self.db.refresh(item)
        return items

    def set_item_payment(
        self,
        item_id: int,
        amount_paid: Decimal,
        paid_at: datetime | None = None,
    ) -> CapitalCallItem | None:
        item = (
            self.db.query(CapitalCallItem).filter(CapitalCallItem.id == item_id).first()
        )
        if item is None:
            return None
        item.amount_paid = amount_paid
        item.paid_at = paid_at
        self.db.flush()
        self._commitments.recompute_totals(item.commitment_id)  # type: ignore[invalid-argument-type]
        self.recompute_status(item.capital_call_id)  # type: ignore[invalid-argument-type]
        self.db.commit()
        self.db.refresh(item)
        return item

    def update_item(
        self,
        item_id: int,
        *,
        amount_due: Decimal | None = None,
        amount_paid: Decimal | None = None,
        paid_at: datetime | None = None,
        paid_at_set: bool = False,
        note: str | None = None,
        note_set: bool = False,
    ) -> CapitalCallItem | None:
        item = (
            self.db.query(CapitalCallItem).filter(CapitalCallItem.id == item_id).first()
        )
        if item is None:
            return None
        if amount_due is not None:
            item.amount_due = amount_due
        if amount_paid is not None:
            item.amount_paid = amount_paid
        if paid_at_set:
            item.paid_at = paid_at
        if note_set:
            item.note = note
        self.db.flush()
        self._commitments.recompute_totals(item.commitment_id)  # type: ignore[invalid-argument-type]
        self.recompute_status(item.capital_call_id)  # type: ignore[invalid-argument-type]
        self.db.commit()
        self.db.refresh(item)
        return item

    def transition_status(
        self, call_id: int, new_status: CapitalCallStatus
    ) -> CapitalCall | None:
        call = self.db.query(CapitalCall).filter(CapitalCall.id == call_id).first()
        if call is None:
            return None
        current = call.status
        if current == new_status:
            return self.get_with_items(call_id)
        allowed = _ALLOWED_TRANSITIONS.get(current, set())  # type: ignore[invalid-argument-type]
        if new_status not in allowed:
            raise ValueError(
                f"Cannot transition capital call from '{current.value}' "
                f"to '{new_status.value}'"
            )
        call.status = new_status
        self.db.commit()
        return self.get_with_items(call_id)

    def recompute_status(self, call_id: int) -> CapitalCall | None:
        call = self.db.query(CapitalCall).filter(CapitalCall.id == call_id).first()
        if call is None:
            return None
        if call.status in _TERMINAL_STATUSES:
            return call
        # Don't auto-transition out of pre-send statuses; payments shouldn't
        # promote a draft/scheduled call.
        if call.status in {CapitalCallStatus.draft, CapitalCallStatus.scheduled}:
            return call
        totals = (
            self.db.query(
                func.coalesce(func.sum(CapitalCallItem.amount_due), 0),
                func.coalesce(func.sum(CapitalCallItem.amount_paid), 0),
            )
            .filter(CapitalCallItem.capital_call_id == call_id)
            .one()
        )
        total_due = Decimal(totals[0] or 0)
        total_paid = Decimal(totals[1] or 0)
        if total_due > Decimal("0") and total_paid >= total_due:
            new_status = CapitalCallStatus.paid
        elif total_paid > Decimal("0"):
            new_status = CapitalCallStatus.partially_paid
        else:
            # Preserve overdue / sent state when nothing is paid.
            new_status = call.status
        if new_status != call.status:
            call.status = new_status
        self.db.flush()
        return call

    def send(self, call_id: int) -> CapitalCall | None:
        call = self.db.query(CapitalCall).filter(CapitalCall.id == call_id).first()
        if call is None:
            return None
        if call.status not in _SENDABLE_STATUSES:
            raise ValueError(
                f"Cannot send capital call in status '{call.status.value}'"
            )
        call.status = CapitalCallStatus.sent
        if call.call_date is None:
            call.call_date = datetime.now(timezone.utc).date()
        self.db.commit()
        return self.get_with_items(call_id)

    def cancel(self, call_id: int) -> CapitalCall | None:
        return self.transition_status(call_id, CapitalCallStatus.cancelled)
