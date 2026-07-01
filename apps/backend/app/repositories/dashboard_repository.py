import uuid
from datetime import date
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Query, Session

from app.models import (
    CapitalCall,
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
    DashboardOverviewResponse,
    FundSummary,
)

OUTSTANDING_CAPITAL_CALL_STATUSES = (
    CapitalCallStatus.scheduled,
    CapitalCallStatus.sent,
    CapitalCallStatus.partially_paid,
)

_ORG_VISIBLE_ROLES = (UserRole.admin, UserRole.fund_manager, UserRole.superadmin)


class DashboardRepository:
    def __init__(self, db: Session):
        self.db = db
        self._memberships = UserOrganizationMembershipRepository(db)

    def _empty_response(self) -> DashboardOverviewResponse:
        return DashboardOverviewResponse(
            funds_active=0,
            investors_total=0,
            commitments_total_amount=Decimal("0"),
            capital_calls_outstanding=0,
            distributions_ytd_amount=Decimal("0"),
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
        if header_org_id is not None:
            membership = self._memberships.get(user.id, header_org_id)  # type: ignore[invalid-argument-type]
            if membership is not None:
                return membership
            if user.role == UserRole.superadmin:
                return UserOrganizationMembership(
                    user_id=user.id,
                    organization_id=header_org_id,
                    role=UserRole.superadmin,
                )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not a member of this organization",
            )
        if user.role == UserRole.superadmin:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="X-Organization-Id required",
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
            func.coalesce(func.sum(Commitment.committed_amount), 0)
        )
        if membership.role in _ORG_VISIBLE_ROLES:
            commitments_q = self._scope_by_fund(
                commitments_q, Commitment.fund_id, fund_filter
            )
        else:
            commitments_q = self._scope_by_investor(
                commitments_q, Commitment.investor_id, investor_filter
            )
        commitments_total_amount = commitments_q.scalar()

        capital_calls_q = db.query(func.count(CapitalCall.id)).filter(
            CapitalCall.status.in_(OUTSTANDING_CAPITAL_CALL_STATUSES)
        )
        capital_calls_outstanding = (
            self._scope_by_fund(
                capital_calls_q, CapitalCall.fund_id, fund_filter
            ).scalar()
            or 0
        )

        year_start = date(date.today().year, 1, 1)
        distributions_q = (
            db.query(func.coalesce(func.sum(DistributionItem.amount_paid), 0))
            .join(Distribution, Distribution.id == DistributionItem.distribution_id)
            .filter(DistributionItem.paid_at >= year_start)
        )
        distributions_ytd_amount = self._scope_by_fund(
            distributions_q, Distribution.fund_id, fund_filter
        ).scalar()

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

        recent_funds = [
            FundSummary(
                id=fund.id,
                name=fund.name,
                vintage_year=fund.vintage_year,
                strategy=fund.strategy,
                status=fund.status,
                currency_code=fund.currency_code,
                committed_amount=Decimal(str(committed)),
                called_amount=Decimal(str(called)),
                irr=None,
                tvpi=None,
            )
            for fund, committed, called in fund_rows
        ]

        upcoming_q = (
            db.query(CapitalCall, Fund.name)
            .join(Fund, Fund.id == CapitalCall.fund_id)
            .filter(CapitalCall.status.in_(OUTSTANDING_CAPITAL_CALL_STATUSES))
        )
        upcoming_rows = (
            self._scope_by_fund(upcoming_q, Fund.id, fund_filter)
            .order_by(CapitalCall.due_date.asc())
            .limit(5)
            .all()
        )

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
            commitments_total_amount=Decimal(str(commitments_total_amount)),
            capital_calls_outstanding=capital_calls_outstanding,
            distributions_ytd_amount=Decimal(str(distributions_ytd_amount)),
            unread_notifications_count=unread_notifications_count,
            open_tasks_count=open_tasks_count,
            recent_funds=recent_funds,
            upcoming_capital_calls=upcoming_capital_calls,
            recent_communications=recent_communications,
        )
