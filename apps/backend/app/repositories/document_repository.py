import logging
import uuid

from sqlalchemy import or_, select
from sqlalchemy.orm import Query, Session, joinedload

from app.models.commitment import Commitment
from app.models.document import Document
from app.models.enums import DocumentType, UserRole
from app.models.fund import Fund
from app.models.investor_contact import InvestorContact
from app.models.user_organization_membership import UserOrganizationMembership
from app.repositories.lp_scope import lp_visible_investor_ids
from app.schemas.document import DocumentCreate, DocumentUpdate
from app.services.storage import get_storage, key_from_file_url

_ORG_VISIBLE_ROLES = (UserRole.admin, UserRole.fund_manager)

logger = logging.getLogger(__name__)


class DocumentRepository:
    def __init__(self, db: Session):
        self.db = db

    def _base_query(self) -> Query:
        return self.db.query(Document).options(
            joinedload(Document.fund),
            joinedload(Document.investor),
        )

    def _visibility_filter(
        self, query: Query, membership: UserOrganizationMembership
    ) -> Query:
        if membership.role in _ORG_VISIBLE_ROLES:
            org_id = membership.organization_id
            visible_fund_ids = select(Fund.id).where(Fund.organization_id == org_id)
            return query.filter(
                or_(
                    Document.organization_id == org_id,
                    Document.fund_id.in_(visible_fund_ids),
                    Document.uploaded_by_user_id == membership.user_id,
                )
            )
        # LP: only docs scoped to investors they're a contact for, plus
        # non-confidential docs on funds they hold a commitment in.
        visible_investor_ids = lp_visible_investor_ids(membership)
        visible_fund_ids = select(Commitment.fund_id).where(
            Commitment.investor_id.in_(lp_visible_investor_ids(membership))
        )
        return query.filter(
            or_(
                Document.investor_id.in_(visible_investor_ids),
                Document.uploaded_by_user_id == membership.user_id,
                ~Document.is_confidential & Document.fund_id.in_(visible_fund_ids),
            )
        )

    def list_for_membership(
        self,
        membership: UserOrganizationMembership,
        *,
        organization_id: uuid.UUID | None = None,
        fund_id: uuid.UUID | None = None,
        investor_id: uuid.UUID | None = None,
        document_type: DocumentType | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Document]:
        query = self._visibility_filter(self._base_query(), membership)
        if organization_id is not None:
            query = query.filter(Document.organization_id == organization_id)
        if fund_id is not None:
            query = query.filter(Document.fund_id == fund_id)
        if investor_id is not None:
            query = query.filter(Document.investor_id == investor_id)
        if document_type is not None:
            query = query.filter(Document.document_type == document_type)
        return (
            query.order_by(Document.created_at.desc(), Document.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get(self, document_id: uuid.UUID) -> Document | None:
        return self._base_query().filter(Document.id == document_id).first()

    def membership_can_view(
        self, membership: UserOrganizationMembership, document: Document
    ) -> bool:
        if membership.role in _ORG_VISIBLE_ROLES:
            if document.uploaded_by_user_id == membership.user_id:
                return True
            if (
                document.organization_id is not None
                and document.organization_id == membership.organization_id
            ):
                return True
            if document.fund_id is not None:
                fund = self.db.query(Fund).filter(Fund.id == document.fund_id).first()
                return bool(
                    fund is not None
                    and fund.organization_id == membership.organization_id
                )
            return False
        # LP
        if document.uploaded_by_user_id == membership.user_id:
            return True
        if document.investor_id is not None:
            return (
                self.db.query(InvestorContact.id)
                .filter(
                    InvestorContact.investor_id == document.investor_id,
                    InvestorContact.investor_id.in_(
                        lp_visible_investor_ids(membership)
                    ),
                )
                .first()
                is not None
            )
        if not document.is_confidential and document.fund_id is not None:
            return (
                self.db.query(Commitment.id)
                .filter(
                    Commitment.fund_id == document.fund_id,
                    Commitment.investor_id.in_(lp_visible_investor_ids(membership)),
                )
                .first()
                is not None
            )
        return False

    def membership_can_manage(
        self, membership: UserOrganizationMembership, document: Document
    ) -> bool:
        if membership.role not in _ORG_VISIBLE_ROLES:
            return False
        if document.uploaded_by_user_id == membership.user_id:
            return True
        if (
            document.organization_id is not None
            and document.organization_id == membership.organization_id
        ):
            return True
        if document.fund_id is not None:
            fund = self.db.query(Fund).filter(Fund.id == document.fund_id).first()
            return bool(
                fund is not None and fund.organization_id == membership.organization_id
            )
        return False

    def recipient_contacts(self, document: Document) -> list[InvestorContact]:
        """Investor contacts covered by the document's LP visibility rule.

        Investor-scoped documents are always visible to that investor, so all
        of its contacts qualify. Fund-only documents are visible to LPs only
        when non-confidential; recipients are the primary contacts of
        investors holding a commitment in the fund. Callers project the piece
        they need (``user_id`` for in-app notifications, ``email`` for mail).
        """
        if document.investor_id is not None:
            return (
                self.db.query(InvestorContact)
                .filter(InvestorContact.investor_id == document.investor_id)
                .all()
            )
        if document.fund_id is not None and not document.is_confidential:
            return (
                self.db.query(InvestorContact)
                .join(
                    Commitment,
                    Commitment.investor_id == InvestorContact.investor_id,
                )
                .filter(
                    Commitment.fund_id == document.fund_id,
                    InvestorContact.is_primary.is_(True),
                )
                .distinct()
                .all()
            )
        return []

    def create(
        self,
        data: DocumentCreate,
        *,
        uploaded_by_user_id: uuid.UUID | None = None,
        commit: bool = True,
    ) -> Document:
        """Add (and by default commit) one ``Document``.

        ``commit=False`` lets a caller (see ``EmailIngestService.ingest``)
        fold several of these into one transaction alongside other writes, so
        a failure partway through leaves nothing committed instead of the
        earlier rows landing while the rest are lost.
        """
        document = Document(
            **data.model_dump(),
            uploaded_by_user_id=uploaded_by_user_id,
        )
        self.db.add(document)
        if commit:
            self.db.commit()
            self.db.refresh(document)
        return document

    def update(self, document_id: uuid.UUID, data: DocumentUpdate) -> Document | None:
        document = self.get(document_id)
        if document is None:
            return None
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(document, key, value)
        self.db.commit()
        self.db.refresh(document)
        return document

    def delete(self, document_id: uuid.UUID) -> bool:
        document = self.get(document_id)
        if document is None:
            return False
        file_url = document.file_url
        self.db.delete(document)
        self.db.commit()
        # Best-effort blob cleanup after the row is gone: the DB is the
        # source of truth, and an orphaned blob beats a phantom row pointing
        # at a deleted file.
        if file_url:
            try:
                get_storage().delete(key_from_file_url(file_url))  # type: ignore[invalid-argument-type]
            except Exception:
                logger.warning(
                    "Failed to delete stored file for document %s",
                    document_id,
                    exc_info=True,
                )
        return True
