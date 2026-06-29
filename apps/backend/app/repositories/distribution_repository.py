from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Query, Session, joinedload

from app.models.commitment import Commitment
from app.models.distribution import Distribution
from app.models.distribution_item import DistributionItem
from app.models.enums import DistributionStatus, UserRole
from app.models.fund import Fund
from app.models.investor_contact import InvestorContact
from app.models.user_organization_membership import UserOrganizationMembership
from app.repositories.commitment_repository import CommitmentRepository
from app.schemas.distribution import DistributionCreate, DistributionUpdate

_ORG_VISIBLE_ROLES = (UserRole.admin, UserRole.fund_manager, UserRole.superadmin)

_SENDABLE_STATUSES = {DistributionStatus.draft, DistributionStatus.scheduled}
_TERMINAL_STATUSES = {DistributionStatus.cancelled}
_ALLOWED_TRANSITIONS: dict[DistributionStatus, set[DistributionStatus]] = {
    DistributionStatus.draft: {
        DistributionStatus.scheduled,
        DistributionStatus.sent,
        DistributionStatus.cancelled,
    },
    DistributionStatus.scheduled: {
        DistributionStatus.sent,
        DistributionStatus.cancelled,
    },
    DistributionStatus.sent: {
        DistributionStatus.partially_paid,
        DistributionStatus.paid,
        DistributionStatus.cancelled,
    },
    DistributionStatus.partially_paid: {
        DistributionStatus.paid,
        DistributionStatus.cancelled,
    },
    DistributionStatus.paid: set(),
    DistributionStatus.cancelled: set(),
}


class DistributionRepository:
    def __init__(self, db: Session):
        self.db = db
        self._commitments = CommitmentRepository(db)

    def _base_query(self) -> Query:
        return self.db.query(Distribution).options(
            joinedload(Distribution.items),
            joinedload(Distribution.fund),
        )

    def list_for_membership(
        self,
        membership: UserOrganizationMembership,
        *,
        fund_id: int | None = None,
        status: DistributionStatus | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Distribution]:
        query = self._base_query()
        if membership.role in _ORG_VISIBLE_ROLES:
            query = query.join(Fund, Fund.id == Distribution.fund_id).filter(
                Fund.organization_id == membership.organization_id
            )
        else:
            visible_investor_ids = select(InvestorContact.investor_id).where(
                InvestorContact.user_id == membership.user_id
            )
            visible_distribution_ids = (
                select(DistributionItem.distribution_id)
                .join(
                    Commitment,
                    Commitment.id == DistributionItem.commitment_id,
                )
                .where(Commitment.investor_id.in_(visible_investor_ids))
            )
            query = query.filter(Distribution.id.in_(visible_distribution_ids))
        if fund_id is not None:
            query = query.filter(Distribution.fund_id == fund_id)
        if status is not None:
            query = query.filter(Distribution.status == status)
        return query.order_by(Distribution.id).offset(skip).limit(limit).all()

    def get_with_items(self, distribution_id: int) -> Distribution | None:
        return self._base_query().filter(Distribution.id == distribution_id).first()

    def membership_can_view(
        self, membership: UserOrganizationMembership, distribution: Distribution
    ) -> bool:
        if membership.role in _ORG_VISIBLE_ROLES:
            fund = self.db.query(Fund).filter(Fund.id == distribution.fund_id).first()
            if fund is None:
                return False
            return bool(fund.organization_id == membership.organization_id)
        return (
            self.db.query(DistributionItem.id)
            .join(Commitment, Commitment.id == DistributionItem.commitment_id)
            .join(
                InvestorContact,
                InvestorContact.investor_id == Commitment.investor_id,
            )
            .filter(
                DistributionItem.distribution_id == distribution.id,
                InvestorContact.user_id == membership.user_id,
            )
            .first()
            is not None
        )

    def create_draft(
        self,
        data: DistributionCreate,
        *,
        created_by_user_id: int | None = None,
    ) -> Distribution:
        distribution = Distribution(
            fund_id=data.fund_id,
            title=data.title,
            description=data.description,
            distribution_date=data.distribution_date,
            record_date=data.record_date,
            amount=data.amount,
            status=DistributionStatus.draft,
            created_by_user_id=created_by_user_id,
        )
        self.db.add(distribution)
        self.db.commit()
        self.db.refresh(distribution)
        return distribution

    def update(
        self, distribution_id: int, data: DistributionUpdate
    ) -> Distribution | None:
        distribution = (
            self.db.query(Distribution)
            .filter(Distribution.id == distribution_id)
            .first()
        )
        if distribution is None:
            return None
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(distribution, key, value)
        self.db.commit()
        self.db.refresh(distribution)
        return self.get_with_items(distribution_id)

    def add_items(
        self,
        distribution_id: int,
        allocations: list[tuple[int, Decimal]],
    ) -> list[DistributionItem]:
        """Bulk-insert allocations on the distribution.

        `allocations` is a list of `(commitment_id, amount_due)` tuples.
        Rejects entries whose commitment belongs to a different fund or that
        duplicate an existing allocation for the distribution.
        """
        distribution = (
            self.db.query(Distribution)
            .filter(Distribution.id == distribution_id)
            .first()
        )
        if distribution is None:
            raise ValueError("Distribution not found")
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
            if commitment.fund_id != distribution.fund_id:
                raise ValueError(
                    f"Commitment {commitment_id} does not belong to fund "
                    f"{distribution.fund_id}"
                )
        existing = (
            self.db.query(DistributionItem.commitment_id)
            .filter(DistributionItem.distribution_id == distribution_id)
            .all()
        )
        existing_ids = {row[0] for row in existing}
        for commitment_id, _ in allocations:
            if commitment_id in existing_ids:
                raise ValueError(
                    f"Allocation for commitment {commitment_id} already exists"
                )
        items = [
            DistributionItem(
                distribution_id=distribution_id,
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
    ) -> DistributionItem | None:
        item = (
            self.db.query(DistributionItem)
            .filter(DistributionItem.id == item_id)
            .first()
        )
        if item is None:
            return None
        item.amount_paid = amount_paid
        item.paid_at = paid_at
        self.db.flush()
        self._commitments.recompute_totals(item.commitment_id)  # type: ignore[invalid-argument-type]
        self.recompute_status(item.distribution_id)  # type: ignore[invalid-argument-type]
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
    ) -> DistributionItem | None:
        item = (
            self.db.query(DistributionItem)
            .filter(DistributionItem.id == item_id)
            .first()
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
        self.recompute_status(item.distribution_id)  # type: ignore[invalid-argument-type]
        self.db.commit()
        self.db.refresh(item)
        return item

    def transition_status(
        self, distribution_id: int, new_status: DistributionStatus
    ) -> Distribution | None:
        distribution = (
            self.db.query(Distribution)
            .filter(Distribution.id == distribution_id)
            .first()
        )
        if distribution is None:
            return None
        current = distribution.status
        if current == new_status:
            return self.get_with_items(distribution_id)
        allowed = _ALLOWED_TRANSITIONS.get(current, set())  # type: ignore[invalid-argument-type]
        if new_status not in allowed:
            raise ValueError(
                f"Cannot transition distribution from '{current.value}' "
                f"to '{new_status.value}'"
            )
        distribution.status = new_status
        self.db.commit()
        return self.get_with_items(distribution_id)

    def recompute_status(self, distribution_id: int) -> Distribution | None:
        distribution = (
            self.db.query(Distribution)
            .filter(Distribution.id == distribution_id)
            .first()
        )
        if distribution is None:
            return None
        if distribution.status in _TERMINAL_STATUSES:
            return distribution
        # Don't auto-transition out of pre-send statuses; payments shouldn't
        # promote a draft/scheduled distribution.
        if distribution.status in {
            DistributionStatus.draft,
            DistributionStatus.scheduled,
        }:
            return distribution
        totals = (
            self.db.query(
                func.coalesce(func.sum(DistributionItem.amount_due), 0),
                func.coalesce(func.sum(DistributionItem.amount_paid), 0),
            )
            .filter(DistributionItem.distribution_id == distribution_id)
            .one()
        )
        total_due = Decimal(totals[0] or 0)
        total_paid = Decimal(totals[1] or 0)
        if total_due > Decimal("0") and total_paid >= total_due:
            new_status = DistributionStatus.paid
        elif total_paid > Decimal("0"):
            new_status = DistributionStatus.partially_paid
        else:
            new_status = distribution.status
        if new_status != distribution.status:
            distribution.status = new_status
        self.db.flush()
        return distribution

    def send(self, distribution_id: int) -> Distribution | None:
        distribution = (
            self.db.query(Distribution)
            .filter(Distribution.id == distribution_id)
            .first()
        )
        if distribution is None:
            return None
        if distribution.status not in _SENDABLE_STATUSES:
            raise ValueError(
                f"Cannot send distribution in status '{distribution.status.value}'"
            )
        distribution.status = DistributionStatus.sent
        if distribution.record_date is None:
            distribution.record_date = datetime.now(timezone.utc).date()
        self.db.commit()
        return self.get_with_items(distribution_id)

    def cancel(self, distribution_id: int) -> Distribution | None:
        return self.transition_status(distribution_id, DistributionStatus.cancelled)
