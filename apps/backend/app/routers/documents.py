import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.rbac import (
    get_active_membership,
    get_current_user_record,
    require_membership_roles,
)
from app.models.enums import DocumentType, UserRole
from app.models.user import User
from app.models.user_organization_membership import UserOrganizationMembership
from app.repositories.document_repository import DocumentRepository
from app.repositories.fund_repository import FundRepository
from app.repositories.investor_repository import InvestorRepository
from app.repositories.organization_repository import OrganizationRepository
from app.schemas.document import (
    DocumentCreate,
    DocumentDraftLetterResponse,
    DocumentRead,
    DocumentUpdate,
    DocumentUploadInit,
    DocumentUploadInitResponse,
)
from app.services.notifications import notify_document_uploaded
from app.services.storage import (
    LocalDevStorage,
    get_storage,
    key_from_file_url,
)
from app.tasks import enqueue_draft_letter

router = APIRouter(dependencies=[Depends(get_current_user)])

_ORG_ROLES = (UserRole.admin, UserRole.fund_manager)


def _generate_storage_key(file_name: str) -> str:
    """Build a storage key with a random prefix to avoid collisions."""
    safe_name = file_name.strip().replace("/", "_") or "upload.bin"
    token = secrets.token_urlsafe(16)
    return f"documents/{token}/{safe_name}"


def _ensure_can_attach(
    membership: UserOrganizationMembership,
    db: Session,
    data: DocumentCreate,
) -> None:
    """Reject creates that point at orgs/funds/investors the caller can't manage."""
    if membership.role not in _ORG_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins and fund managers can create documents",
        )
    org_id = membership.organization_id
    if data.organization_id is not None and data.organization_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot attach document to a different organization",
        )
    if data.fund_id is not None:
        fund_row = FundRepository(db).get(data.fund_id)
        if fund_row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Fund not found"
            )
        if fund_row[0].organization_id != org_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot attach document to a fund outside your organization",
            )
    if data.investor_id is not None:
        investor_row = InvestorRepository(db).get(data.investor_id)
        if investor_row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Investor not found"
            )
        if investor_row[0].organization_id != org_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot attach document to an investor outside your organization",
            )


def _to_read(document) -> DocumentRead:
    storage = get_storage()
    download_url: str | None = None
    if document.file_url:
        try:
            download_url = storage.presign_get(key_from_file_url(document.file_url))
        except Exception:
            download_url = document.file_url
    return DocumentRead(
        id=document.id,
        organization_id=document.organization_id,
        fund_id=document.fund_id,
        fund_name=document.fund.name if document.fund is not None else None,
        investor_id=document.investor_id,
        investor_name=(
            document.investor.name if document.investor is not None else None
        ),
        uploaded_by_user_id=document.uploaded_by_user_id,
        document_type=document.document_type,
        title=document.title,
        file_name=document.file_name,
        file_url=document.file_url,
        download_url=download_url,
        mime_type=document.mime_type,
        file_size=document.file_size,
        is_confidential=document.is_confidential,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


@router.post(
    "/upload-init",
    response_model=DocumentUploadInitResponse,
    status_code=status.HTTP_201_CREATED,
)
async def init_document_upload(
    payload: DocumentUploadInit,
    # Every role may stage an upload — plain authentication is enough.
    current_user: User = Depends(get_current_user_record),
):
    storage = get_storage()
    key = _generate_storage_key(payload.file_name)
    upload_url, file_url, expires_at = storage.presign_put(key, payload.mime_type)
    return DocumentUploadInitResponse(
        upload_url=upload_url, file_url=file_url, expires_at=expires_at
    )


_MAX_UPLOAD_BYTES = 100 * 1024 * 1024


@router.put("/upload/{key:path}", status_code=status.HTTP_204_NO_CONTENT)
async def upload_document_bytes(
    key: str,
    request: Request,
    # Same bar as upload-init: any authenticated user may push bytes for a
    # key that upload-init handed them.
    current_user: User = Depends(get_current_user_record),
):
    """Proxy upload: write the raw request body to the storage backend.

    The S3 backend routes uploads here (see ``S3Storage.presign_put``) so the
    browser never talks to the bucket directly and no bucket CORS
    configuration is needed — the bytes travel through the API, which already
    allows the app origins.
    """
    if ".." in key.split("/") or key.startswith("/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid storage key"
        )
    body = await request.body()
    if len(body) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File exceeds the 100 MB upload limit",
        )
    storage = get_storage()
    storage.write(key, body, request.headers.get("content-type"))
    return None


@router.post("", response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
async def create_document(
    data: DocumentCreate,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(get_active_membership),
):
    _ensure_can_attach(membership, db, data)
    if data.organization_id is not None:
        org = OrganizationRepository(db).get(data.organization_id)
        if org is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found"
            )
    repo = DocumentRepository(db)
    document = repo.create(data, uploaded_by_user_id=membership.user_id)  # type: ignore[invalid-argument-type]
    await notify_document_uploaded(db, document=document)
    return _to_read(document)


@router.get("", response_model=list[DocumentRead])
async def list_documents(
    organization_id: uuid.UUID | None = None,
    fund_id: uuid.UUID | None = None,
    investor_id: uuid.UUID | None = None,
    document_type: DocumentType | None = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(get_active_membership),
):
    repo = DocumentRepository(db)
    documents = repo.list_for_membership(
        membership,
        organization_id=organization_id,
        fund_id=fund_id,
        investor_id=investor_id,
        document_type=document_type,
        skip=skip,
        limit=limit,
    )
    return [_to_read(doc) for doc in documents]


@router.get("/{document_id}", response_model=DocumentRead)
async def get_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(get_active_membership),
):
    repo = DocumentRepository(db)
    document = repo.get(document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )
    if not repo.membership_can_view(membership, document):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot view this document",
        )
    return _to_read(document)


@router.patch("/{document_id}", response_model=DocumentRead)
async def update_document(
    document_id: uuid.UUID,
    data: DocumentUpdate,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(
        require_membership_roles(UserRole.admin, UserRole.fund_manager)
    ),
):
    repo = DocumentRepository(db)
    document = repo.get(document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )
    if not repo.membership_can_manage(membership, document):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot edit this document",
        )
    updated = repo.update(document_id, data)
    assert updated is not None
    return _to_read(updated)


@router.post(
    "/{document_id}/draft-letter",
    response_model=DocumentDraftLetterResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def draft_letter_from_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(
        require_membership_roles(UserRole.admin, UserRole.fund_manager)
    ),
):
    """Queue an AI letter draft from a document.

    Runs in the worker (Claude on a multi-page PDF is slow); the draft lands in
    the Letters area as a Communication and the requester is notified when
    ready. 404 when the feature is off (no ``OPENROUTER_API_KEY``).
    """
    if not settings.letter_drafting_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI letter drafting is not enabled",
        )
    repo = DocumentRepository(db)
    document = repo.get(document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )
    if not repo.membership_can_manage(membership, document):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot draft a letter from this document",
        )
    await enqueue_draft_letter(
        document_id=str(document_id), user_id=str(membership.user_id)
    )
    return DocumentDraftLetterResponse()


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(
        require_membership_roles(UserRole.admin, UserRole.fund_manager)
    ),
):
    repo = DocumentRepository(db)
    document = repo.get(document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )
    if not repo.membership_can_manage(membership, document):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete this document",
        )
    repo.delete(document_id)
    return None


# ---- Local dev storage endpoint -------------------------------------------
#
# Mounted in ``app.main`` (NOT under ``/documents`` and NOT behind the JWT
# auth dependency) so the LocalDevStorage backend's presigned PUTs work
# without forcing test/dev clients to re-attach the Hanko bearer token.

dev_storage_router = APIRouter()


def _dev_storage_only() -> LocalDevStorage:
    storage = get_storage()
    if not isinstance(storage, LocalDevStorage):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Dev storage not enabled"
        )
    return storage


@dev_storage_router.put(
    "/dev-storage/{key:path}", status_code=status.HTTP_204_NO_CONTENT
)
@dev_storage_router.post(
    "/dev-storage/{key:path}", status_code=status.HTTP_204_NO_CONTENT
)
async def dev_storage_upload(key: str, request: Request):
    """Accept raw bytes for a presigned key. Dev-only; protected by a header token."""
    storage = _dev_storage_only()
    expected = settings.DEV_STORAGE_TOKEN
    provided = request.headers.get("x-dev-storage-token")
    if not expected or provided != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid dev storage token",
        )
    body = await request.body()
    storage.write(key, body)
    return None


@dev_storage_router.get("/dev-storage/{key:path}")
async def dev_storage_download(key: str):
    storage = _dev_storage_only()
    blob = storage.read(key)
    if blob is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Object not found"
        )
    return Response(content=blob, media_type="application/octet-stream")
