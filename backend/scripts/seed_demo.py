"""Idempotent demo seed for screenshots, demos, and end-to-end smoke runs.

Run from the repo root via ``make seed`` (or ``cd backend && uv run python -m
scripts.seed_demo``). Re-running produces the same dataset — every entity is
keyed on a deterministic field (org name, user email, fund name, investor
name) and skipped if it already exists.

Goes through the same repository constructors that the API uses so role
defaults, status transitions, and pro-rata allocation logic stay in sync.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.audit import record_audit
from app.core.database import SessionLocal, init_db
from app.middleware.audit_context import set_audit_context
from app.models.audit_log import AuditLog
from app.models.capital_call import CapitalCall
from app.models.capital_call_item import CapitalCallItem
from app.models.commitment import Commitment
from app.models.communication import Communication
from app.models.distribution import Distribution
from app.models.distribution_item import DistributionItem
from app.models.document import Document
from app.models.enums import (
    CapitalCallStatus,
    CommitmentStatus,
    CommunicationType,
    DistributionStatus,
    DocumentType,
    FundStatus,
    NotificationStatus,
    OrganizationType,
    TaskStatus,
    UserRole,
)
from app.models.fund import Fund
from app.models.fund_group import FundGroup
from app.models.investor import Investor
from app.models.investor_contact import InvestorContact
from app.models.notification import Notification
from app.models.organization import Organization
from app.models.task import Task
from app.models.user import User
from app.repositories.capital_call_repository import CapitalCallRepository
from app.repositories.commitment_repository import CommitmentRepository
from app.repositories.communication_repository import CommunicationRepository
from app.repositories.distribution_repository import DistributionRepository
from app.repositories.document_repository import DocumentRepository
from app.repositories.fund_group_repository import FundGroupRepository
from app.repositories.fund_repository import FundRepository
from app.repositories.investor_contact_repository import InvestorContactRepository
from app.repositories.investor_repository import InvestorRepository
from app.repositories.notification_repository import NotificationRepository
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.task_repository import TaskRepository
from app.repositories.user_repository import UserRepository
from app.schemas.capital_call import CapitalCallCreate
from app.schemas.commitment import CommitmentCreate
from app.schemas.communication import CommunicationCreate
from app.schemas.distribution import DistributionCreate
from app.schemas.document import DocumentCreate
from app.schemas.fund import FundCreate
from app.schemas.fund_group import FundGroupCreate
from app.schemas.investor import InvestorCreate
from app.schemas.investor_contact import InvestorContactCreate
from app.schemas.organization import OrganizationCreate
from app.schemas.task import TaskCreate, TaskUpdate
from app.schemas.user import UserCreate


def _get_or_create_organization(
    db: Session, *, name: str, type: OrganizationType, **extra
) -> Organization:
    existing = db.query(Organization).filter(Organization.name == name).first()
    if existing is not None:
        return existing
    repo = OrganizationRepository(db)
    return repo.create(OrganizationCreate(name=name, type=type, **extra))


def _get_or_create_user(
    db: Session,
    *,
    email: str,
    role: UserRole,
    first_name: str,
    last_name: str,
    organization_id: int | None,
    title: str | None = None,
) -> User:
    repo = UserRepository(db)
    existing = repo.get_by_email(email)
    if existing is not None:
        return existing
    return repo.create(
        UserCreate(
            organization_id=organization_id,
            role=role,
            first_name=first_name,
            last_name=last_name,
            email=email,
            title=title,
        )
    )


def _get_or_create_fund_group(
    db: Session,
    *,
    name: str,
    organization_id: int,
    description: str | None,
    created_by_user_id: int | None,
) -> FundGroup:
    existing = (
        db.query(FundGroup)
        .filter(
            FundGroup.organization_id == organization_id,
            FundGroup.name == name,
        )
        .first()
    )
    if existing is not None:
        return existing
    repo = FundGroupRepository(db)
    return repo.create(
        FundGroupCreate(
            organization_id=organization_id,
            name=name,
            description=description,
        ),
        created_by_user_id=created_by_user_id,
    )


def _get_or_create_fund(
    db: Session,
    *,
    name: str,
    organization_id: int,
    fund_group_id: int,
    vintage_year: int,
    target_size: Decimal,
    status: FundStatus,
    strategy: str,
    inception_date: date,
) -> Fund:
    existing = (
        db.query(Fund)
        .filter(Fund.organization_id == organization_id, Fund.name == name)
        .first()
    )
    if existing is not None:
        return existing
    repo = FundRepository(db)
    fund, _ = repo.create(
        FundCreate(
            organization_id=organization_id,
            fund_group_id=fund_group_id,
            name=name,
            vintage_year=vintage_year,
            strategy=strategy,
            target_size=target_size,
            status=status,
            inception_date=inception_date,
        )
    )
    return fund


def _get_or_create_investor(
    db: Session,
    *,
    name: str,
    organization_id: int,
    investor_code: str,
    investor_type: str,
    accredited: bool,
) -> Investor:
    existing = (
        db.query(Investor)
        .filter(
            Investor.organization_id == organization_id,
            Investor.name == name,
        )
        .first()
    )
    if existing is not None:
        return existing
    repo = InvestorRepository(db)
    investor, _, _ = repo.create(
        InvestorCreate(
            organization_id=organization_id,
            name=name,
            investor_code=investor_code,
            investor_type=investor_type,
            accredited=accredited,
        )
    )
    return investor


def _get_or_create_primary_contact(
    db: Session,
    *,
    investor_id: int,
    user: User,
) -> InvestorContact:
    existing = (
        db.query(InvestorContact)
        .filter(
            InvestorContact.investor_id == investor_id,
            InvestorContact.user_id == user.id,
        )
        .first()
    )
    if existing is not None:
        return existing
    repo = InvestorContactRepository(db)
    return repo.create(
        investor_id,
        InvestorContactCreate(
            user_id=user.id,  # type: ignore[invalid-argument-type]
            first_name=user.first_name,  # type: ignore[invalid-argument-type]
            last_name=user.last_name,  # type: ignore[invalid-argument-type]
            email=user.email,  # type: ignore[invalid-argument-type]
            phone=user.phone,  # type: ignore[invalid-argument-type]
            title=user.title,  # type: ignore[invalid-argument-type]
            is_primary=True,
        ),
    )


def _get_or_create_commitment(
    db: Session,
    *,
    fund_id: int,
    investor_id: int,
    committed_amount: Decimal,
    commitment_date: date,
    status: CommitmentStatus = CommitmentStatus.approved,
) -> Commitment:
    repo = CommitmentRepository(db)
    existing = repo.get_by_fund_and_investor(fund_id, investor_id)
    if existing is not None:
        return existing
    commitment = repo.create(
        CommitmentCreate(
            fund_id=fund_id,
            investor_id=investor_id,
            committed_amount=committed_amount,
            commitment_date=commitment_date,
            status=status,
        )
    )
    return commitment


def _seed_capital_call(
    db: Session,
    *,
    fund: Fund,
    title: str,
    amount: Decimal,
    due_date: date,
    created_by_user_id: int,
    target_status: CapitalCallStatus,
    paid_fraction: Decimal,
) -> CapitalCall:
    """Create + populate one capital call, leaving it in ``target_status``.

    ``paid_fraction`` is the share of each item's ``amount_due`` to record as
    paid (0.0–1.0). Sent + fully paid uses 1.0; partially_paid uses ~0.5;
    scheduled uses 0.0 and skips the send transition.
    """
    existing = (
        db.query(CapitalCall)
        .filter(CapitalCall.fund_id == fund.id, CapitalCall.title == title)
        .first()
    )
    if existing is not None:
        return existing

    repo = CapitalCallRepository(db)
    call = repo.create_draft(
        CapitalCallCreate(
            fund_id=fund.id,  # type: ignore[arg-type]
            title=title,
            description=f"Auto-seeded {title} for {fund.name}",
            due_date=due_date,
            amount=amount,
        ),
        created_by_user_id=created_by_user_id,
    )

    commitments = (
        db.query(Commitment)
        .filter(
            Commitment.fund_id == fund.id,
            Commitment.status == CommitmentStatus.approved,
        )
        .order_by(Commitment.id)
        .all()
    )
    if not commitments:
        return call

    total = sum(
        (Decimal(c.committed_amount) for c in commitments),  # type: ignore[invalid-argument-type]
        Decimal("0"),
    )
    allocations: list[tuple[int, Decimal]] = []
    running_total = Decimal("0")
    for idx, c in enumerate(commitments):
        if idx == len(commitments) - 1:
            share = (amount - running_total).quantize(Decimal("0.01"))
        else:
            share = (
                amount * Decimal(c.committed_amount) / total  # type: ignore[invalid-argument-type]
            ).quantize(Decimal("0.01"))
            running_total += share
        allocations.append((c.id, share))  # type: ignore[arg-type]
    repo.add_items(call.id, allocations)  # type: ignore[arg-type]

    if target_status is CapitalCallStatus.scheduled:
        repo.transition_status(call.id, CapitalCallStatus.scheduled)  # type: ignore[arg-type]
        return call

    repo.send(call.id)  # type: ignore[arg-type]

    if paid_fraction <= Decimal("0"):
        return call

    paid_at = datetime.now(timezone.utc)
    items = (
        db.query(CapitalCallItem)
        .filter(CapitalCallItem.capital_call_id == call.id)
        .all()
    )
    for item in items:
        amount_paid = (
            Decimal(item.amount_due) * paid_fraction  # type: ignore[invalid-argument-type]
        ).quantize(Decimal("0.01"))
        repo.set_item_payment(item.id, amount_paid, paid_at=paid_at)  # type: ignore[arg-type]
    return call


def _seed_distribution(
    db: Session,
    *,
    fund: Fund,
    title: str,
    amount: Decimal,
    distribution_date: date,
    created_by_user_id: int,
    target_status: DistributionStatus,
    paid_fraction: Decimal,
) -> Distribution:
    existing = (
        db.query(Distribution)
        .filter(Distribution.fund_id == fund.id, Distribution.title == title)
        .first()
    )
    if existing is not None:
        return existing

    repo = DistributionRepository(db)
    distribution = repo.create_draft(
        DistributionCreate(
            fund_id=fund.id,  # type: ignore[arg-type]
            title=title,
            description=f"Auto-seeded {title} for {fund.name}",
            distribution_date=distribution_date,
            amount=amount,
        ),
        created_by_user_id=created_by_user_id,
    )

    commitments = (
        db.query(Commitment)
        .filter(
            Commitment.fund_id == fund.id,
            Commitment.status == CommitmentStatus.approved,
        )
        .order_by(Commitment.id)
        .all()
    )
    if not commitments:
        return distribution

    total = sum(
        (Decimal(c.committed_amount) for c in commitments),  # type: ignore[invalid-argument-type]
        Decimal("0"),
    )
    allocations: list[tuple[int, Decimal]] = []
    running_total = Decimal("0")
    for idx, c in enumerate(commitments):
        if idx == len(commitments) - 1:
            share = (amount - running_total).quantize(Decimal("0.01"))
        else:
            share = (
                amount * Decimal(c.committed_amount) / total  # type: ignore[invalid-argument-type]
            ).quantize(Decimal("0.01"))
            running_total += share
        allocations.append((c.id, share))  # type: ignore[arg-type]
    repo.add_items(distribution.id, allocations)  # type: ignore[arg-type]

    if target_status is DistributionStatus.scheduled:
        repo.transition_status(distribution.id, DistributionStatus.scheduled)  # type: ignore[arg-type]
        return distribution

    repo.send(distribution.id)  # type: ignore[arg-type]

    if paid_fraction <= Decimal("0"):
        return distribution

    paid_at = datetime.now(timezone.utc)
    items = (
        db.query(DistributionItem)
        .filter(DistributionItem.distribution_id == distribution.id)
        .all()
    )
    for item in items:
        amount_paid = (
            Decimal(item.amount_due) * paid_fraction  # type: ignore[invalid-argument-type]
        ).quantize(Decimal("0.01"))
        repo.set_item_payment(item.id, amount_paid, paid_at=paid_at)  # type: ignore[arg-type]
    return distribution


def _seed_document(
    db: Session,
    *,
    title: str,
    file_name: str,
    document_type: DocumentType,
    organization_id: int | None,
    fund_id: int | None,
    investor_id: int | None,
    uploaded_by_user_id: int,
    is_confidential: bool,
) -> Document:
    existing = (
        db.query(Document)
        .filter(Document.title == title, Document.file_name == file_name)
        .first()
    )
    if existing is not None:
        return existing
    repo = DocumentRepository(db)
    return repo.create(
        DocumentCreate(
            organization_id=organization_id,
            fund_id=fund_id,
            investor_id=investor_id,
            document_type=document_type,
            title=title,
            file_name=file_name,
            file_url=f"http://localhost:8000/dev-storage/seed/{file_name}",
            mime_type="application/pdf",
            file_size=128 * 1024,
            is_confidential=is_confidential,
        ),
        uploaded_by_user_id=uploaded_by_user_id,
    )


def _seed_communication(
    db: Session,
    *,
    fund: Fund,
    subject: str,
    body: str,
    sender: User,
    send: bool,
) -> Communication:
    existing = (
        db.query(Communication)
        .filter(Communication.fund_id == fund.id, Communication.subject == subject)
        .first()
    )
    if existing is not None:
        return existing
    repo = CommunicationRepository(db)
    communication = repo.create_draft(
        CommunicationCreate(
            fund_id=fund.id,  # type: ignore[arg-type]
            type=CommunicationType.announcement,
            subject=subject,
            body=body,
        ),
        sender_user_id=sender.id,  # type: ignore[arg-type]
    )
    if not send:
        return communication
    # The default fund-wide expansion needs at least one approved commitment
    # whose investor has a primary contact; that's true in the seeded dataset.
    try:
        repo.send(communication.id)  # type: ignore[arg-type]
    except ValueError:
        # No recipients resolvable yet — fall back to no-op so the seed stays
        # idempotent rather than crashing on partially-seeded state.
        pass
    return communication


def _seed_task(
    db: Session,
    *,
    title: str,
    description: str,
    fund_id: int | None,
    assigned_to_user_id: int | None,
    created_by_user_id: int,
    status: TaskStatus,
    due_date: date | None,
) -> Task:
    existing = (
        db.query(Task)
        .filter(Task.title == title, Task.created_by_user_id == created_by_user_id)
        .first()
    )
    if existing is not None:
        return existing
    repo = TaskRepository(db)
    task = repo.create(
        TaskCreate(
            fund_id=fund_id,
            assigned_to_user_id=assigned_to_user_id,
            title=title,
            description=description,
            status=TaskStatus.open,
            due_date=due_date,
        ),
        created_by_user_id=created_by_user_id,
    )
    if status is not TaskStatus.open:
        repo.update(task.id, TaskUpdate(status=status))  # type: ignore[arg-type]
    return task


def _seed_notification(
    db: Session,
    *,
    user: User,
    title: str,
    message: str,
    related_type: str | None,
    related_id: int | None,
    status: NotificationStatus,
) -> Notification:
    existing = (
        db.query(Notification)
        .filter(Notification.user_id == user.id, Notification.title == title)
        .first()
    )
    if existing is not None:
        return existing
    repo = NotificationRepository(db)
    notification = repo.create(
        user_id=user.id,  # type: ignore[arg-type]
        title=title,
        message=message,
        related_type=related_type,
        related_id=related_id,
    )
    if status is not NotificationStatus.unread:
        notification.status = status
        if status is NotificationStatus.read:
            notification.read_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(notification)
    return notification


def seed(db: Session) -> None:
    """Populate the database with a deterministic demo dataset."""
    # Organizations -------------------------------------------------------
    eden = _get_or_create_organization(
        db,
        name="Eden Capital Partners",
        type=OrganizationType.fund_manager_firm,
        legal_name="Eden Capital Partners LP",
        website="https://eden.example.com",
        description="Mid-market growth equity and venture funds.",
    )
    northstar = _get_or_create_organization(
        db,
        name="Northstar Trust",
        type=OrganizationType.investor_firm,
        legal_name="Northstar Trust Company",
        website="https://northstar.example.com",
        description="Multi-family office allocating to private markets.",
    )
    atlas = _get_or_create_organization(
        db,
        name="Atlas Family Office",
        type=OrganizationType.investor_firm,
        legal_name="Atlas Family Office LLC",
        website="https://atlas.example.com",
        description="Single-family office focused on long-term capital.",
    )

    # Users ---------------------------------------------------------------
    admin = _get_or_create_user(
        db,
        email="admin@edenscale.demo",
        role=UserRole.admin,
        first_name="Alex",
        last_name="Taylor",
        organization_id=eden.id,  # type: ignore[arg-type]
        title="Platform Administrator",
    )
    ava = _get_or_create_user(
        db,
        email="ava.morgan@edenscale.demo",
        role=UserRole.fund_manager,
        first_name="Ava",
        last_name="Morgan",
        organization_id=eden.id,  # type: ignore[arg-type]
        title="Managing Director",
    )
    ben = _get_or_create_user(
        db,
        email="ben.shaw@edenscale.demo",
        role=UserRole.fund_manager,
        first_name="Ben",
        last_name="Shaw",
        organization_id=eden.id,  # type: ignore[arg-type]
        title="Principal",
    )
    carla = _get_or_create_user(
        db,
        email="carla.diaz@northstar.demo",
        role=UserRole.lp,
        first_name="Carla",
        last_name="Diaz",
        organization_id=northstar.id,  # type: ignore[arg-type]
        title="Director of Investments",
    )
    david = _get_or_create_user(
        db,
        email="david.kim@northstar.demo",
        role=UserRole.lp,
        first_name="David",
        last_name="Kim",
        organization_id=northstar.id,  # type: ignore[arg-type]
        title="Portfolio Manager",
    )
    elena = _get_or_create_user(
        db,
        email="elena.park@atlas.demo",
        role=UserRole.lp,
        first_name="Elena",
        last_name="Park",
        organization_id=atlas.id,  # type: ignore[arg-type]
        title="Chief Investment Officer",
    )
    frank = _get_or_create_user(
        db,
        email="frank.lee@atlas.demo",
        role=UserRole.lp,
        first_name="Frank",
        last_name="Lee",
        organization_id=atlas.id,  # type: ignore[arg-type]
        title="Investment Analyst",
    )

    # Fund groups ---------------------------------------------------------
    growth_group = _get_or_create_fund_group(
        db,
        name="Growth Equity",
        organization_id=eden.id,  # type: ignore[arg-type]
        description="Late-stage growth equity vehicles.",
        created_by_user_id=ava.id,  # type: ignore[arg-type]
    )
    venture_group = _get_or_create_fund_group(
        db,
        name="Venture",
        organization_id=eden.id,  # type: ignore[arg-type]
        description="Early- to growth-stage venture vehicles.",
        created_by_user_id=ava.id,  # type: ignore[arg-type]
    )

    # Funds ---------------------------------------------------------------
    growth_i = _get_or_create_fund(
        db,
        name="Eden Growth Fund I",
        organization_id=eden.id,  # type: ignore[arg-type]
        fund_group_id=growth_group.id,  # type: ignore[arg-type]
        vintage_year=2021,
        target_size=Decimal("250000000"),
        status=FundStatus.active,
        strategy="Growth equity, B2B SaaS and fintech",
        inception_date=date(2021, 3, 15),
    )
    growth_ii = _get_or_create_fund(
        db,
        name="Eden Growth Fund II",
        organization_id=eden.id,  # type: ignore[arg-type]
        fund_group_id=growth_group.id,  # type: ignore[arg-type]
        vintage_year=2024,
        target_size=Decimal("400000000"),
        status=FundStatus.active,
        strategy="Growth equity, infrastructure software",
        inception_date=date(2024, 6, 1),
    )
    venture_i = _get_or_create_fund(
        db,
        name="Eden Venture Fund I",
        organization_id=eden.id,  # type: ignore[arg-type]
        fund_group_id=venture_group.id,  # type: ignore[arg-type]
        vintage_year=2022,
        target_size=Decimal("150000000"),
        status=FundStatus.active,
        strategy="Seed and Series A, climate tech",
        inception_date=date(2022, 9, 1),
    )
    venture_ii = _get_or_create_fund(
        db,
        name="Eden Venture Fund II",
        organization_id=eden.id,  # type: ignore[arg-type]
        fund_group_id=venture_group.id,  # type: ignore[arg-type]
        vintage_year=2025,
        target_size=Decimal("200000000"),
        status=FundStatus.draft,
        strategy="Series A and B, AI tooling",
        inception_date=date(2025, 11, 1),
    )

    # Investors + primary contacts ----------------------------------------
    investor_specs = [
        ("Northstar Endowment Pool", northstar, "NS-001", "endowment", carla),
        ("Northstar Pension Trust", northstar, "NS-002", "pension", david),
        ("Northstar Foundation Fund", northstar, "NS-003", "foundation", carla),
        ("Atlas Heritage Fund", atlas, "AT-001", "family_office", elena),
        ("Atlas Legacy Trust", atlas, "AT-002", "family_office", frank),
        ("Atlas Discovery Vehicle", atlas, "AT-003", "family_office", elena),
    ]
    investors: list[Investor] = []
    for name, org, code, kind, contact_user in investor_specs:
        investor = _get_or_create_investor(
            db,
            name=name,
            organization_id=org.id,  # type: ignore[arg-type]
            investor_code=code,
            investor_type=kind,
            accredited=True,
        )
        _get_or_create_primary_contact(
            db, investor_id=investor.id, user=contact_user  # type: ignore[arg-type]
        )
        investors.append(investor)

    # Commitments ---------------------------------------------------------
    # NB: a user that is the primary contact on two investors must not have
    # both investors hold a commitment in the same fund. Otherwise, sending a
    # fund-wide communication tries to insert two recipient rows with the same
    # ``(communication_id, user_id)`` and trips the unique constraint.
    commitment_plan: list[tuple[Investor, Fund, Decimal, date]] = [
        (investors[0], growth_i, Decimal("10000000"), date(2021, 6, 15)),
        (investors[0], venture_i, Decimal("3000000"), date(2022, 10, 1)),
        (investors[1], growth_i, Decimal("8000000"), date(2021, 7, 10)),
        (investors[1], growth_ii, Decimal("12000000"), date(2024, 7, 20)),
        (investors[2], growth_ii, Decimal("5000000"), date(2024, 8, 1)),
        (investors[2], venture_ii, Decimal("4000000"), date(2025, 12, 1)),
        (investors[3], growth_i, Decimal("15000000"), date(2021, 5, 5)),
        (investors[3], growth_ii, Decimal("20000000"), date(2024, 8, 12)),
        (investors[3], venture_i, Decimal("5000000"), date(2022, 11, 5)),
        (investors[4], growth_ii, Decimal("10000000"), date(2024, 9, 1)),
        (investors[4], venture_i, Decimal("4000000"), date(2022, 12, 15)),
        (investors[5], venture_ii, Decimal("6000000"), date(2026, 1, 15)),
    ]
    for investor, fund, amount, when in commitment_plan:
        _get_or_create_commitment(
            db,
            fund_id=fund.id,  # type: ignore[arg-type]
            investor_id=investor.id,  # type: ignore[arg-type]
            committed_amount=amount,
            commitment_date=when,
        )

    # Capital calls -------------------------------------------------------
    today = date.today()
    _seed_capital_call(
        db,
        fund=growth_i,
        title="Capital Call #1 — Initial Drawdown",
        amount=Decimal("5000000"),
        due_date=today - timedelta(days=120),
        created_by_user_id=ava.id,  # type: ignore[arg-type]
        target_status=CapitalCallStatus.paid,
        paid_fraction=Decimal("1.0"),
    )
    _seed_capital_call(
        db,
        fund=growth_i,
        title="Capital Call #2 — Follow-on Investment",
        amount=Decimal("3000000"),
        due_date=today + timedelta(days=15),
        created_by_user_id=ava.id,  # type: ignore[arg-type]
        target_status=CapitalCallStatus.partially_paid,
        paid_fraction=Decimal("0.5"),
    )
    _seed_capital_call(
        db,
        fund=growth_ii,
        title="Capital Call #1 — Fund Operations",
        amount=Decimal("4000000"),
        due_date=today + timedelta(days=45),
        created_by_user_id=ben.id,  # type: ignore[arg-type]
        target_status=CapitalCallStatus.scheduled,
        paid_fraction=Decimal("0"),
    )

    # Distributions -------------------------------------------------------
    _seed_distribution(
        db,
        fund=growth_i,
        title="Q4 2025 Distribution",
        amount=Decimal("2500000"),
        distribution_date=today - timedelta(days=60),
        created_by_user_id=ava.id,  # type: ignore[arg-type]
        target_status=DistributionStatus.paid,
        paid_fraction=Decimal("1.0"),
    )
    _seed_distribution(
        db,
        fund=venture_i,
        title="Realisation: Portfolio Exit Proceeds",
        amount=Decimal("1500000"),
        distribution_date=today + timedelta(days=30),
        created_by_user_id=ben.id,  # type: ignore[arg-type]
        target_status=DistributionStatus.scheduled,
        paid_fraction=Decimal("0"),
    )

    # Documents -----------------------------------------------------------
    _seed_document(
        db,
        title="Eden Growth Fund I — LPA",
        file_name="growth-i-lpa.pdf",
        document_type=DocumentType.legal,
        organization_id=eden.id,  # type: ignore[arg-type]
        fund_id=growth_i.id,  # type: ignore[arg-type]
        investor_id=None,
        uploaded_by_user_id=ava.id,  # type: ignore[arg-type]
        is_confidential=False,
    )
    _seed_document(
        db,
        title="Eden Growth Fund I — Q4 2025 Report",
        file_name="growth-i-q4-2025.pdf",
        document_type=DocumentType.report,
        organization_id=None,
        fund_id=growth_i.id,  # type: ignore[arg-type]
        investor_id=None,
        uploaded_by_user_id=ava.id,  # type: ignore[arg-type]
        is_confidential=False,
    )
    _seed_document(
        db,
        title="Northstar Endowment — KYC Package",
        file_name="ns-endowment-kyc.pdf",
        document_type=DocumentType.kyc_aml,
        organization_id=None,
        fund_id=None,
        investor_id=investors[0].id,  # type: ignore[arg-type]
        uploaded_by_user_id=ben.id,  # type: ignore[arg-type]
        is_confidential=True,
    )
    _seed_document(
        db,
        title="Atlas Heritage Fund — Side Letter",
        file_name="atlas-heritage-sideletter.pdf",
        document_type=DocumentType.legal,
        organization_id=None,
        fund_id=None,
        investor_id=investors[3].id,  # type: ignore[arg-type]
        uploaded_by_user_id=ava.id,  # type: ignore[arg-type]
        is_confidential=True,
    )
    _seed_document(
        db,
        title="Eden Growth Fund II — Audited Financials",
        file_name="growth-ii-audit-2025.pdf",
        document_type=DocumentType.financial,
        organization_id=None,
        fund_id=growth_ii.id,  # type: ignore[arg-type]
        investor_id=None,
        uploaded_by_user_id=ben.id,  # type: ignore[arg-type]
        is_confidential=False,
    )

    # Communications (letters) -------------------------------------------
    _seed_communication(
        db,
        fund=growth_i,
        subject="Q4 2025 LP Letter",
        body="Dear Limited Partners,\n\nThis quarter we deployed capital across "
        "two new platform investments and saw two portfolio companies execute "
        "secondary sales. Detailed financials are attached.",
        sender=ava,
        send=True,
    )
    _seed_communication(
        db,
        fund=growth_i,
        subject="Annual General Meeting — Save the Date",
        body="Our annual LP meeting will be held in person on March 15th. "
        "Registration details and the agenda will follow in two weeks.",
        sender=ava,
        send=True,
    )
    _seed_communication(
        db,
        fund=growth_ii,
        subject="Fund II Final Close Notice",
        body="We're pleased to announce the final close of Eden Growth Fund II "
        "at $400M. Subscription documents have been countersigned.",
        sender=ben,
        send=True,
    )
    _seed_communication(
        db,
        fund=venture_i,
        subject="Portfolio Update: AI Tooling Cohort",
        body="A draft summary of the venture portfolio's AI tooling investments "
        "for your review before the next call.",
        sender=ben,
        send=False,
    )

    # Tasks ---------------------------------------------------------------
    _seed_task(
        db,
        title="Send capital call notice for Growth I CC#3",
        description="Draft notice and circulate to LP relations team for review.",
        fund_id=growth_i.id,  # type: ignore[arg-type]
        assigned_to_user_id=ava.id,  # type: ignore[arg-type]
        created_by_user_id=admin.id,  # type: ignore[arg-type]
        status=TaskStatus.open,
        due_date=today + timedelta(days=7),
    )
    _seed_task(
        db,
        title="Reconcile Q4 wires with prime broker statements",
        description="Confirm that incoming and outgoing wires match the custody report.",
        fund_id=growth_i.id,  # type: ignore[arg-type]
        assigned_to_user_id=ben.id,  # type: ignore[arg-type]
        created_by_user_id=ava.id,  # type: ignore[arg-type]
        status=TaskStatus.in_progress,
        due_date=today + timedelta(days=3),
    )
    _seed_task(
        db,
        title="Refresh Fund II tear sheet for prospect meeting",
        description="Update the latest IRR and DPI numbers in the deck.",
        fund_id=growth_ii.id,  # type: ignore[arg-type]
        assigned_to_user_id=ben.id,  # type: ignore[arg-type]
        created_by_user_id=ava.id,  # type: ignore[arg-type]
        status=TaskStatus.open,
        due_date=today + timedelta(days=14),
    )
    _seed_task(
        db,
        title="Approve Atlas Heritage side letter v3",
        description="Legal returned redlines on the side letter — please review.",
        fund_id=growth_i.id,  # type: ignore[arg-type]
        assigned_to_user_id=ava.id,  # type: ignore[arg-type]
        created_by_user_id=ben.id,  # type: ignore[arg-type]
        status=TaskStatus.open,
        due_date=today + timedelta(days=2),
    )
    _seed_task(
        db,
        title="Sign FATCA acknowledgement",
        description="Annual FATCA paperwork is due before quarter end.",
        fund_id=None,
        assigned_to_user_id=carla.id,  # type: ignore[arg-type]
        created_by_user_id=ava.id,  # type: ignore[arg-type]
        status=TaskStatus.open,
        due_date=today + timedelta(days=21),
    )
    _seed_task(
        db,
        title="Confirm wire instructions for next capital call",
        description="Verify with treasury that the wire path is unchanged.",
        fund_id=None,
        assigned_to_user_id=elena.id,  # type: ignore[arg-type]
        created_by_user_id=ava.id,  # type: ignore[arg-type]
        status=TaskStatus.open,
        due_date=today + timedelta(days=10),
    )
    _seed_task(
        db,
        title="Onboard new portfolio analyst",
        description="Schedule kickoff calls and provision accounts.",
        fund_id=None,
        assigned_to_user_id=admin.id,  # type: ignore[arg-type]
        created_by_user_id=admin.id,  # type: ignore[arg-type]
        status=TaskStatus.in_progress,
        due_date=today + timedelta(days=5),
    )
    _seed_task(
        db,
        title="Archive 2023 board materials",
        description="Move closed deals from active workspace to archive.",
        fund_id=None,
        assigned_to_user_id=ben.id,  # type: ignore[arg-type]
        created_by_user_id=admin.id,  # type: ignore[arg-type]
        status=TaskStatus.done,
        due_date=today - timedelta(days=10),
    )

    # Notifications -------------------------------------------------------
    _seed_notification(
        db,
        user=carla,
        title="New capital call: Growth I CC#2",
        message="A capital call for Eden Growth Fund I is due in 15 days.",
        related_type="capital_call",
        related_id=None,
        status=NotificationStatus.unread,
    )
    _seed_notification(
        db,
        user=david,
        title="New distribution: Growth I Q4 2025",
        message="A distribution from Eden Growth Fund I has been paid.",
        related_type="distribution",
        related_id=None,
        status=NotificationStatus.unread,
    )
    _seed_notification(
        db,
        user=elena,
        title="Document available: Heritage Side Letter",
        message="A new side letter has been shared with Atlas Heritage Fund.",
        related_type="document",
        related_id=None,
        status=NotificationStatus.unread,
    )
    _seed_notification(
        db,
        user=frank,
        title="Welcome to EdenScale",
        message="Your investor portal access is ready — explore your commitments.",
        related_type=None,
        related_id=None,
        status=NotificationStatus.read,
    )
    _seed_notification(
        db,
        user=ava,
        title="Capital call CC#2 partially paid",
        message="Two of three commitments have funded the second drawdown.",
        related_type="capital_call",
        related_id=None,
        status=NotificationStatus.unread,
    )
    _seed_notification(
        db,
        user=ben,
        title="Task assigned: Reconcile Q4 wires",
        message="Ava assigned you a reconciliation task due in three days.",
        related_type="task",
        related_id=None,
        status=NotificationStatus.unread,
    )

    # Login audit entry ---------------------------------------------------
    # Adds a non-mutation audit row so the admin viewer's "login" filter has
    # at least one row to surface in the demo dataset.
    if (
        db.query(AuditLog)
        .filter(AuditLog.action == "login", AuditLog.user_id == ava.id)
        .first()
        is None
    ):
        record_audit(
            db,
            user=ava,
            action="login",
            entity_type="session",
            entity_id=None,
            metadata={"reason": "seed_demo"},
        )


def main() -> None:
    init_db()
    db: Session = SessionLocal()
    # Attach a "system" audit context so seeded inserts are attributable to
    # something other than a stale request scope.
    set_audit_context(user_id=None, ip_address="127.0.0.1")
    try:
        seed(db)
        print("Demo dataset seeded.")
        print(
            "Sign-in emails (claim them via Hanko on first login):\n"
            "  admin                : admin@edenscale.demo\n"
            "  fund_manager (Eden)  : ava.morgan@edenscale.demo\n"
            "  fund_manager (Eden)  : ben.shaw@edenscale.demo\n"
            "  lp (Northstar)       : carla.diaz@northstar.demo\n"
            "  lp (Northstar)       : david.kim@northstar.demo\n"
            "  lp (Atlas)           : elena.park@atlas.demo\n"
            "  lp (Atlas)           : frank.lee@atlas.demo"
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
