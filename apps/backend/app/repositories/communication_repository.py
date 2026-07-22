import uuid
from datetime import datetime, timezone

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Query, Session, selectinload

from app.models.commitment import Commitment
from app.models.communication import Communication
from app.models.communication_recipient import CommunicationRecipient
from app.models.enums import CommitmentStatus, CommunicationType, UserRole
from app.models.fund import Fund
from app.models.investor import Investor
from app.models.investor_contact import InvestorContact
from app.models.user_organization_membership import UserOrganizationMembership
from app.repositories.lp_scope import lp_visible_contact_ids
from app.schemas.communication import (
    CommunicationCreate,
    CommunicationRecipientRef,
    CommunicationUpdate,
)

_ORG_VISIBLE_ROLES = (UserRole.admin, UserRole.fund_manager)


class CommunicationRepository:
    def __init__(self, db: Session):
        self.db = db

    def _base_query(self) -> Query:
        return self.db.query(Communication).options(
            selectinload(Communication.recipients),
        )

    def list_for_membership(
        self,
        membership: UserOrganizationMembership,
        *,
        fund_id: uuid.UUID | None = None,
        comm_type: CommunicationType | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Communication]:
        query = self._base_query()
        if membership.role in _ORG_VISIBLE_ROLES:
            org_fund_ids = select(Fund.id).where(
                Fund.organization_id == membership.organization_id
            )
            query = query.filter(
                or_(
                    Communication.sender_user_id == membership.user_id,
                    Communication.fund_id.in_(org_fund_ids),
                )
            )
        else:
            visible_recipient_comm_ids = select(
                CommunicationRecipient.communication_id
            ).where(
                or_(
                    CommunicationRecipient.user_id == membership.user_id,
                    CommunicationRecipient.investor_contact_id.in_(
                        lp_visible_contact_ids(membership)
                    ),
                )
            )
            # Drafts (sent_at IS NULL) never reach an LP through recipient
            # visibility. Recipient rows are only written by send(), so this is
            # belt-and-braces today — but it keeps the guarantee from resting on
            # that one insertion site.
            query = query.filter(
                or_(
                    Communication.sender_user_id == membership.user_id,
                    and_(
                        Communication.id.in_(visible_recipient_comm_ids),
                        Communication.sent_at.is_not(None),
                    ),
                )
            )
        if fund_id is not None:
            query = query.filter(Communication.fund_id == fund_id)
        if comm_type is not None:
            query = query.filter(Communication.type == comm_type)
        return (
            query.order_by(Communication.created_at.desc(), Communication.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def list_recent_for_membership(
        self, membership: UserOrganizationMembership, *, limit: int = 5
    ) -> list[Communication]:
        """Sent communications visible to the active membership, newest first.

        Used by the dashboard overview — shares scoping with
        :meth:`list_for_membership` but filters to ``sent_at IS NOT NULL`` so
        drafts don't leak into the activity feed.
        """
        query = self.db.query(Communication)
        if membership.role in _ORG_VISIBLE_ROLES:
            org_fund_ids = select(Fund.id).where(
                Fund.organization_id == membership.organization_id
            )
            query = query.filter(
                or_(
                    Communication.sender_user_id == membership.user_id,
                    Communication.fund_id.in_(org_fund_ids),
                )
            )
        else:
            visible_recipient_comm_ids = select(
                CommunicationRecipient.communication_id
            ).where(
                or_(
                    CommunicationRecipient.user_id == membership.user_id,
                    CommunicationRecipient.investor_contact_id.in_(
                        lp_visible_contact_ids(membership)
                    ),
                )
            )
            query = query.filter(
                or_(
                    Communication.sender_user_id == membership.user_id,
                    Communication.id.in_(visible_recipient_comm_ids),
                )
            )
        return (
            query.filter(Communication.sent_at.is_not(None))
            .order_by(Communication.sent_at.desc(), Communication.id.desc())
            .limit(limit)
            .all()
        )

    def get(self, communication_id: uuid.UUID) -> Communication | None:
        return self._base_query().filter(Communication.id == communication_id).first()

    def membership_can_view(
        self, membership: UserOrganizationMembership, communication: Communication
    ) -> bool:
        if communication.sender_user_id == membership.user_id:
            return True
        if membership.role in _ORG_VISIBLE_ROLES:
            if communication.fund_id is None:
                return False
            fund = self.db.query(Fund).filter(Fund.id == communication.fund_id).first()
            return bool(
                fund is not None and fund.organization_id == membership.organization_id
            )
        # LP: visible if they are a recipient (directly or via investor contact)
        # and the communication has actually been sent — never a draft.
        if communication.sent_at is None:
            return False
        own_contact_ids = lp_visible_contact_ids(membership)
        return (
            self.db.query(CommunicationRecipient.id)
            .filter(
                CommunicationRecipient.communication_id == communication.id,
                or_(
                    CommunicationRecipient.user_id == membership.user_id,
                    CommunicationRecipient.investor_contact_id.in_(own_contact_ids),
                ),
            )
            .first()
            is not None
        )

    def membership_can_manage(
        self, membership: UserOrganizationMembership, communication: Communication
    ) -> bool:
        if membership.role not in _ORG_VISIBLE_ROLES:
            return False
        if communication.sender_user_id == membership.user_id:
            return True
        if communication.fund_id is None:
            return False
        fund = self.db.query(Fund).filter(Fund.id == communication.fund_id).first()
        return bool(
            fund is not None and fund.organization_id == membership.organization_id
        )

    def create_draft(
        self, data: CommunicationCreate, *, sender_user_id: uuid.UUID | None = None
    ) -> Communication:
        communication = Communication(
            fund_id=data.fund_id,
            document_id=data.document_id,
            sender_user_id=sender_user_id,
            type=data.type,
            subject=data.subject,
            body=data.body,
        )
        self.db.add(communication)
        self.db.commit()
        self.db.refresh(communication)
        return communication

    def get_draft_for_document(
        self, document_id: uuid.UUID, *, sender_user_id: uuid.UUID | None
    ) -> Communication | None:
        """The AI-drafted announcement (if any) already generated from this
        document for this requester -- see ``task_draft_letter``, which uses
        this to avoid re-drafting (and re-billing OpenRouter for) a job arq
        redelivers after a crash between ``create_draft`` and the task
        returning."""
        return (
            self.db.query(Communication)
            .filter(
                Communication.document_id == document_id,
                Communication.sender_user_id == sender_user_id,
                Communication.type == CommunicationType.announcement,
            )
            .first()
        )

    def update(
        self, communication_id: uuid.UUID, data: CommunicationUpdate
    ) -> Communication | None:
        communication = (
            self.db.query(Communication)
            .filter(Communication.id == communication_id)
            .first()
        )
        if communication is None:
            return None
        if communication.sent_at is not None:
            raise ValueError("Cannot edit a communication that has already been sent")
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(communication, key, value)
        self.db.commit()
        self.db.refresh(communication)
        return self.get(communication_id)

    def resolve_default_recipients(
        self, fund_id: uuid.UUID
    ) -> list[tuple[uuid.UUID | None, uuid.UUID | None]]:
        """Expand a fund into one (user_id, investor_contact_id) per primary
        contact whose investor holds an approved commitment in the fund.

        Returns a list ordered for stable insertion. Each tuple represents one
        recipient row; either side may be None if a contact has no linked user
        or — exotically — if a user has no associated contact.
        """
        rows = (
            self.db.query(InvestorContact.id, InvestorContact.user_id)
            .join(Commitment, Commitment.investor_id == InvestorContact.investor_id)
            .filter(
                Commitment.fund_id == fund_id,
                Commitment.status == CommitmentStatus.approved,
                InvestorContact.is_primary.is_(True),
            )
            .order_by(InvestorContact.created_at, InvestorContact.id)
            .all()
        )
        return [(user_id, contact_id) for contact_id, user_id in rows]

    def default_recipient_contacts(
        self, fund_id: uuid.UUID
    ) -> list[tuple[InvestorContact, Investor]]:
        """The primary contacts a fund-scoped send would reach, with investor.

        The display counterpart to :meth:`resolve_default_recipients` (which
        returns bare id pairs for insertion): same population — primary contacts
        of investors holding an approved commitment in the fund — but carrying
        the contact + investor rows so the UI can preview names and emails.
        """
        return (
            self.db.query(InvestorContact, Investor)
            .join(Investor, Investor.id == InvestorContact.investor_id)
            .join(Commitment, Commitment.investor_id == InvestorContact.investor_id)
            .filter(
                Commitment.fund_id == fund_id,
                Commitment.status == CommitmentStatus.approved,
                InvestorContact.is_primary.is_(True),
            )
            .order_by(InvestorContact.created_at, InvestorContact.id)
            .all()  # type: ignore[invalid-return-type]
        )

    def send(
        self,
        communication_id: uuid.UUID,
        *,
        explicit_recipients: list[CommunicationRecipientRef] | None = None,
    ) -> Communication | None:
        communication = (
            self.db.query(Communication)
            .filter(Communication.id == communication_id)
            .first()
        )
        if communication is None:
            return None
        if communication.sent_at is not None:
            raise ValueError("Communication already sent")

        recipient_pairs: list[tuple[uuid.UUID | None, uuid.UUID | None]]
        if explicit_recipients:
            recipient_pairs = [
                (ref.user_id, ref.investor_contact_id) for ref in explicit_recipients
            ]
        elif communication.fund_id is not None:
            recipient_pairs = self.resolve_default_recipients(
                communication.fund_id  # type: ignore[invalid-argument-type]
            )
        else:
            raise ValueError(
                "Cannot send communication without a fund_id or explicit recipients"
            )

        if not recipient_pairs:
            raise ValueError("No recipients resolved for this communication")

        seen: set[tuple[uuid.UUID | None, uuid.UUID | None]] = set()
        deduped: list[tuple[uuid.UUID | None, uuid.UUID | None]] = []
        for pair in recipient_pairs:
            if pair in seen:
                continue
            seen.add(pair)
            deduped.append(pair)

        now = datetime.now(timezone.utc)
        communication.sent_at = now
        for user_id, contact_id in deduped:
            recipient = CommunicationRecipient(
                communication_id=communication.id,
                user_id=user_id,
                investor_contact_id=contact_id,
                delivered_at=now,
            )
            self.db.add(recipient)
        self.db.commit()
        return self.get(communication_id)

    def mark_recipient_read(
        self, communication_id: uuid.UUID, recipient_id: uuid.UUID
    ) -> CommunicationRecipient | None:
        recipient = (
            self.db.query(CommunicationRecipient)
            .filter(
                CommunicationRecipient.id == recipient_id,
                CommunicationRecipient.communication_id == communication_id,
            )
            .first()
        )
        if recipient is None:
            return None
        if recipient.read_at is None:
            recipient.read_at = datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(recipient)
        return recipient
