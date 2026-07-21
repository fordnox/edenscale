import uuid
from datetime import date
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Query, Session

from app.models import (
    CapitalCall,
    CapitalCallItem,
    CapitalCallStatus,
    Commitment,
    Distribution,
    DistributionItem,
    Fund,
    FundStatus,
    Investor,
    Notification,
    NotificationStatus,
    Task,
    TaskStatus,
    User,
    UserRole,
)
from app.models.user_organization_membership import UserOrganizationMembership
from app.repositories.communication_repository import CommunicationRepository
from app.repositories.lp_scope import lp_visible_investor_ids
from app.repositories.user_organization_membership_repository import (
    UserOrganizationMembershipRepository,
)
from app.schemas.dashboard import (
    CapitalCallSummary,
    CommunicationSummary,
    CurrencyTotal,
    DashboardOverviewResponse,
    FundSummary,
)
from app.services.metrics import fund_metrics_bulk

OUTSTANDING_CAPITAL_CALL_STATUSES = (
    CapitalCallStatus.scheduled,
    CapitalCallStatus.sent,
    CapitalCallStatus.partially_paid,
)

_ORG_VISIBLE_ROLES = (UserRole.admin, UserRole.fund_manager)


class DashboardRepository:
    def __init__(self, db: Session):
        self.db = db
        self._memberships = UserOrganizationMembershipRepository(db)

    def _empty_response(self) -> DashboardOverviewResponse:
        return DashboardOverviewResponse(
            funds_active=0,
            investors_total=0,
            commitments_by_currency=[],
            capital_calls_outstanding=0,
            distributions_ytd_by_currency=[],
            unread_notifications_count=0,
            open_tasks_count=0,
            recent_funds=[],
            upcoming_capital_calls=[],
            recent_communications=[],
        )

    def resolve_active_membership(
        self, user: User, header_org_id: uuid.UUID | None
    ) -> UserOrganizationMembership | None:
        """Resolve the dashboard's active membership, tolerating no-membership users.

        The dashboard is the one org-scoped surface that historically returned zeros
        for users with no organization. We preserve that here by returning None
        instead of raising 400 when the user has zero memberships and didn't pass
        a header.
        """
        if user.is_superadmin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Superadmins must use /superadmin endpoints",
            )
        if header_org_id is not None:
            membership = self._memberships.get(user.id, header_org_id)  # type: ignore[invalid-argument-type]
            if membership is not None:
                return membership
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not a member of this organization",
            )
        memberships = self._memberships.list_for_user(user.id)  # type: ignore[invalid-argument-type]
        if len(memberships) == 1:
            return memberships[0]
        if not memberships:
            return None
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Organization-Id required",
        )

    def _visible_fund_ids(self, membership: UserOrganizationMembership) -> Select:
        """Subquery yielding fund ids the membership can see."""
        if membership.role in _ORG_VISIBLE_ROLES:
            return select(Fund.id).where(
                Fund.organization_id == membership.organization_id
            )
        return select(Commitment.fund_id).where(
            Commitment.investor_id.in_(lp_visible_investor_ids(membership))
        )

    def _visible_investor_ids(self, membership: UserOrganizationMembership) -> Select:
        """Subquery yielding investor ids the membership can see."""
        if membership.role in _ORG_VISIBLE_ROLES:
            return select(Investor.id).where(
                Investor.organization_id == membership.organization_id
            )
        return lp_visible_investor_ids(membership)

    def _scope_by_fund(
        self, query: Query, fund_id_column, fund_filter: Select
    ) -> Query:
        return query.filter(fund_id_column.in_(fund_filter))

    def _scope_by_investor(
        self, query: Query, investor_id_column, investor_filter: Select
    ) -> Query:
        return query.filter(investor_id_column.in_(investor_filter))

    def get_overview(
        self, user: User, header_org_id: uuid.UUID | None
    ) -> DashboardOverviewResponse:
        membership = self.resolve_active_membership(user, header_org_id)
        if membership is None:
            return self._empty_response()
        return self.get_overview_for_membership(membership)

    def get_overview_for_membership(
        self, membership: UserOrganizationMembership
    ) -> DashboardOverviewResponse:
        """Overview scoped by an already-resolved membership — also the entry
        point for the investor portal, which resolves access from contact
        links rather than membership rows."""
        db = self.db
        fund_filter = self._visible_fund_ids(membership)
        investor_filter = self._visible_investor_ids(membership)

        funds_active_q = db.query(func.count(Fund.id)).filter(
            Fund.status == FundStatus.active
        )
        funds_active = (
            self._scope_by_fund(funds_active_q, Fund.id, fund_filter).scalar() or 0
        )

        investors_total_q = db.query(func.count(Investor.id))
        investors_total = (
            self._scope_by_investor(
                investors_total_q, Investor.id, investor_filter
            ).scalar()
            or 0
        )

        commitments_q = db.query(
            Fund.currency_code,
            func.coalesce(func.sum(Commitment.committed_amount), 0),
        ).join(Fund, Fund.id == Commitment.fund_id)
        if membership.role in _ORG_VISIBLE_ROLES:
            commitments_q = self._scope_by_fund(
                commitments_q, Commitment.fund_id, fund_filter
            )
        else:
            commitments_q = self._scope_by_investor(
                commitments_q, Commitment.investor_id, investor_filter
            )
        commitment_rows = (
            commitments_q.group_by(Fund.currency_code)
            .order_by(Fund.currency_code)
            .all()
        )
        commitments_by_currency = [
            CurrencyTotal(currency_code=currency, amount=Decimal(str(amount)))
            for currency, amount in commitment_rows
        ]

        # LPs get figures for their own allocations (calls that include one of
        # their items; distribution items on their commitments) rather than
        # fund-wide aggregates — the labels on the LP dashboard claim personal
        # numbers.
        capital_calls_q = db.query(func.count(CapitalCall.id)).filter(
            CapitalCall.status.in_(OUTSTANDING_CAPITAL_CALL_STATUSES)
        )
        if membership.role in _ORG_VISIBLE_ROLES:
            capital_calls_q = self._scope_by_fund(
                capital_calls_q, CapitalCall.fund_id, fund_filter
            )
        else:
            lp_call_ids = (
                select(CapitalCallItem.capital_call_id)
                .join(Commitment, Commitment.id == CapitalCallItem.commitment_id)
                .where(Commitment.investor_id.in_(investor_filter))
            )
            capital_calls_q = capital_calls_q.filter(CapitalCall.id.in_(lp_call_ids))
        capital_calls_outstanding = capital_calls_q.scalar() or 0

        year_start = date(date.today().year, 1, 1)
        distributions_q = (
            db.query(
                Fund.currency_code,
                func.coalesce(func.sum(DistributionItem.amount_paid), 0),
            )
            .join(Distribution, Distribution.id == DistributionItem.distribution_id)
            .join(Fund, Fund.id == Distribution.fund_id)
            .filter(DistributionItem.paid_at >= year_start)
        )
        if membership.role in _ORG_VISIBLE_ROLES:
            distributions_q = self._scope_by_fund(
                distributions_q, Distribution.fund_id, fund_filter
            )
        else:
            distributions_q = distributions_q.join(
                Commitment, Commitment.id == DistributionItem.commitment_id
            ).filter(Commitment.investor_id.in_(investor_filter))
        distribution_rows = (
            distributions_q.group_by(Fund.currency_code)
            .order_by(Fund.currency_code)
            .all()
        )
        distributions_ytd_by_currency = [
            CurrencyTotal(currency_code=currency, amount=Decimal(str(amount)))
            for currency, amount in distribution_rows
        ]

        fund_agg_subq = (
            db.query(
                Commitment.fund_id.label("fund_id"),
                func.coalesce(func.sum(Commitment.committed_amount), 0).label(
                    "committed_amount"
                ),
                func.coalesce(func.sum(Commitment.called_amount), 0).label(
                    "called_amount"
                ),
            )
            # Scope to the visible funds inside the subquery rather than
            # relying on the outer join (via _scope_by_fund) to discard the
            # rest of the platform's commitment rows. Results are unchanged.
            .filter(Commitment.fund_id.in_(fund_filter))
            .group_by(Commitment.fund_id)
            .subquery()
        )

        fund_rows_q = db.query(
            Fund,
            func.coalesce(fund_agg_subq.c.committed_amount, 0).label(
                "committed_amount"
            ),
            func.coalesce(fund_agg_subq.c.called_amount, 0).label("called_amount"),
        ).outerjoin(fund_agg_subq, fund_agg_subq.c.fund_id == Fund.id)
        fund_rows = (
            self._scope_by_fund(fund_rows_q, Fund.id, fund_filter)
            .order_by(Fund.created_at.desc())
            .limit(5)
            .all()
        )

        metrics_by_fund = fund_metrics_bulk(db, [fund.id for fund, _, _ in fund_rows])
        recent_funds = []
        for fund, committed, called in fund_rows:
            metrics = metrics_by_fund[fund.id]
            recent_funds.append(
                FundSummary(
                    id=fund.id,
                    name=fund.name,
                    vintage_year=fund.vintage_year,
                    strategy=fund.strategy,
                    status=fund.status,
                    currency_code=fund.currency_code,
                    committed_amount=Decimal(str(committed)),
                    called_amount=Decimal(str(called)),
                    irr=metrics.irr,
                    dpi=metrics.dpi,
                )
            )

        upcoming_q = (
            db.query(CapitalCall, Fund.name)
            .join(Fund, Fund.id == CapitalCall.fund_id)
            .filter(CapitalCall.status.in_(OUTSTANDING_CAPITAL_CALL_STATUSES))
        )
        if membership.role in _ORG_VISIBLE_ROLES:
            upcoming_q = self._scope_by_fund(upcoming_q, Fund.id, fund_filter)
        else:
            lp_upcoming_ids = (
                select(CapitalCallItem.capital_call_id)
                .join(Commitment, Commitment.id == CapitalCallItem.commitment_id)
                .where(Commitment.investor_id.in_(investor_filter))
            )
            upcoming_q = upcoming_q.filter(CapitalCall.id.in_(lp_upcoming_ids))
        upcoming_rows = upcoming_q.order_by(CapitalCall.due_date.asc()).limit(5).all()

        upcoming_capital_calls = [
            CapitalCallSummary(
                id=call.id,
                fund_id=call.fund_id,
                fund_name=fund_name,
                title=call.title,
                amount=call.amount,
                due_date=call.due_date,
                status=call.status,
            )
            for call, fund_name in upcoming_rows
        ]

        unread_notifications_count = (
            db.query(func.count(Notification.id))
            .filter(
                Notification.user_id == membership.user_id,
                Notification.status == NotificationStatus.unread,
            )
            .scalar()
            or 0
        )

        open_tasks_count = (
            db.query(func.count(Task.id))
            .filter(
                Task.assigned_to_user_id == membership.user_id,
                Task.status.in_((TaskStatus.open, TaskStatus.in_progress)),
            )
            .scalar()
            or 0
        )

        communications = CommunicationRepository(db).list_recent_for_membership(
            membership, limit=5
        )
        recent_communications = [
            CommunicationSummary.model_validate(comm) for comm in communications
        ]

        return DashboardOverviewResponse(
            funds_active=funds_active,
            investors_total=investors_total,
            commitments_by_currency=commitments_by_currency,
            capital_calls_outstanding=capital_calls_outstanding,
            distributions_ytd_by_currency=distributions_ytd_by_currency,
            unread_notifications_count=unread_notifications_count,
            open_tasks_count=open_tasks_count,
            recent_funds=recent_funds,
            upcoming_capital_calls=upcoming_capital_calls,
            recent_communications=recent_communications,
        )
