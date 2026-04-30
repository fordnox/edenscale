from sqlalchemy import or_, select
from sqlalchemy.orm import Query, Session

from app.models.commitment import Commitment
from app.models.document import Document
from app.models.enums import DocumentType, UserRole
from app.models.fund import Fund
from app.models.investor_contact import InvestorContact
from app.models.user import User
from app.schemas.document import DocumentCreate, DocumentUpdate


class DocumentRepository:
    def __init__(self, db: Session):
        self.db = db

    def _base_query(self) -> Query:
        return self.db.query(Document)

    def _visibility_filter(self, query: Query, user: User) -> Query:
        if user.role is UserRole.admin:
            return query
        if user.role is UserRole.fund_manager:
            org_id = user.organization_id
            if org_id is None:
                return query.filter(Document.id == -1)
            visible_fund_ids = select(Fund.id).where(Fund.organization_id == org_id)
            return query.filter(
                or_(
                    Document.organization_id == org_id,
                    Document.fund_id.in_(visible_fund_ids),
                    Document.uploaded_by_user_id == user.id,
                )
            )
        # LP: only docs scoped to investors they're a contact for, plus
        # non-confidential docs on funds they hold a commitment in.
        visible_investor_ids = select(InvestorContact.investor_id).where(
            InvestorContact.user_id == user.id
        )
        visible_fund_ids = (
            select(Commitment.fund_id)
            .join(
                InvestorContact,
                InvestorContact.investor_id == Commitment.investor_id,
            )
            .where(InvestorContact.user_id == user.id)
        )
        return query.filter(
            or_(
                Document.investor_id.in_(visible_investor_ids),
                Document.uploaded_by_user_id == user.id,
                ~Document.is_confidential & Document.fund_id.in_(visible_fund_ids),
            )
        )

    def list_for_user(
        self,
        user: User,
        *,
        organization_id: int | None = None,
        fund_id: int | None = None,
        investor_id: int | None = None,
        document_type: DocumentType | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Document]:
        query = self._visibility_filter(self._base_query(), user)
        if organization_id is not None:
            query = query.filter(Document.organization_id == organization_id)
        if fund_id is not None:
            query = query.filter(Document.fund_id == fund_id)
        if investor_id is not None:
            query = query.filter(Document.investor_id == investor_id)
        if document_type is not None:
            query = query.filter(Document.document_type == document_type)
        return query.order_by(Document.id.desc()).offset(skip).limit(limit).all()

    def get(self, document_id: int) -> Document | None:
        return self._base_query().filter(Document.id == document_id).first()

    def user_can_view(self, user: User, document: Document) -> bool:
        if user.role is UserRole.admin:
            return True
        if user.role is UserRole.fund_manager:
            if document.uploaded_by_user_id == user.id:
                return True
            if (
                document.organization_id is not None
                and document.organization_id == user.organization_id
            ):
                return True
            if document.fund_id is not None:
                fund = self.db.query(Fund).filter(Fund.id == document.fund_id).first()
                return bool(
                    fund is not None and fund.organization_id == user.organization_id
                )
            return False
        # LP
        if document.uploaded_by_user_id == user.id:
            return True
        if document.investor_id is not None:
            return (
                self.db.query(InvestorContact.id)
                .filter(
                    InvestorContact.investor_id == document.investor_id,
                    InvestorContact.user_id == user.id,
                )
                .first()
                is not None
            )
        if not document.is_confidential and document.fund_id is not None:
            return (
                self.db.query(Commitment.id)
                .join(
                    InvestorContact,
                    InvestorContact.investor_id == Commitment.investor_id,
                )
                .filter(
                    Commitment.fund_id == document.fund_id,
                    InvestorContact.user_id == user.id,
                )
                .first()
                is not None
            )
        return False

    def user_can_manage(self, user: User, document: Document) -> bool:
        if user.role is UserRole.admin:
            return True
        if user.role is UserRole.fund_manager:
            if document.uploaded_by_user_id == user.id:
                return True
            if (
                document.organization_id is not None
                and document.organization_id == user.organization_id
            ):
                return True
            if document.fund_id is not None:
                fund = self.db.query(Fund).filter(Fund.id == document.fund_id).first()
                return bool(
                    fund is not None and fund.organization_id == user.organization_id
                )
            return False
        return False

    def create(
        self, data: DocumentCreate, *, uploaded_by_user_id: int | None = None
    ) -> Document:
        document = Document(
            **data.model_dump(),
            uploaded_by_user_id=uploaded_by_user_id,
        )
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)
        return document

    def update(self, document_id: int, data: DocumentUpdate) -> Document | None:
        document = self.get(document_id)
        if document is None:
            return None
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(document, key, value)
        self.db.commit()
        self.db.refresh(document)
        return document

    def delete(self, document_id: int) -> bool:
        document = self.get(document_id)
        if document is None:
            return False
        self.db.delete(document)
        self.db.commit()
        return True
