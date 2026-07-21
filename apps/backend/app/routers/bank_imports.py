"""Import capital-call payments from an ISO 20022 bank statement.

Flow: a manager uploads a camt.05x XML (``POST /capital-call-imports``); we
parse its credits, persist them as a pending import, and return each
transaction with suggested capital-call-item matches. The manager reviews in a
wizard and confirms assignments (``POST /capital-call-imports/{id}/apply``),
which writes the payments onto the items and promotes the calls.
"""

import secrets
import uuid
from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.core.rbac import get_active_membership, require_membership_roles
from app.models.bank_statement_import import BankStatementImport
from app.models.enums import BankPaymentTransactionStatus, UserRole
from app.models.user_organization_membership import UserOrganizationMembership
from app.repositories.bank_import_repository import BankImportRepository
from app.schemas.bank_import import (
    ApplyImportRequest,
    BankImportListItem,
    BankImportRead,
    BankTransactionRead,
)
from app.services.iso20022 import Iso20022ParseError, parse_camt
from app.services.payment_matching import suggest_matches
from app.services.storage import get_storage, key_from_file_url

router = APIRouter(dependencies=[Depends(get_current_user)])

_MANAGE_ROLES = (UserRole.admin, UserRole.fund_manager)
_MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # bank statements are text; 25 MB is ample
_UPLOAD_CHUNK_BYTES = 1024 * 1024


async def _read_upload_within_limit(file: UploadFile, max_bytes: int) -> bytes:
    """Read ``file`` in chunks, aborting with 413 once ``max_bytes`` is
    exceeded, instead of one unbounded ``await file.read()`` that would
    already hold an oversized payload in memory before any size check runs.
    Mirrors the streaming enforcement in ``documents.py``'s upload proxy.
    """
    chunks = bytearray()
    while True:
        chunk = await file.read(_UPLOAD_CHUNK_BYTES)
        if not chunk:
            break
        chunks.extend(chunk)
        if len(chunks) > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="File exceeds the 25 MB upload limit",
            )
    return bytes(chunks)


def _generate_storage_key(file_name: str) -> str:
    safe_name = file_name.strip().replace("/", "_") or "statement.xml"
    token = secrets.token_urlsafe(16)
    return f"bank-imports/{token}/{safe_name}"


def _store_raw_file(file_name: str, content: bytes) -> str | None:
    """Persist the raw statement for audit; never fail the import if storage does."""
    try:
        storage = get_storage()
        key = _generate_storage_key(file_name)
        _upload_url, file_url, _expires = storage.presign_put(key, "application/xml")
        storage.write(key_from_file_url(file_url), content, "application/xml")
        return file_url
    except Exception:
        return None


def _to_read(
    db: Session,
    record: BankStatementImport,
    *,
    with_candidates: bool,
) -> BankImportRead:
    read = BankImportRead.model_validate(record)
    transactions = sorted(
        record.transactions,
        key=lambda t: (t.value_date or date.min, t.bank_reference),
    )
    reads = [BankTransactionRead.model_validate(t) for t in transactions]
    if with_candidates:
        pending = [
            t
            for t in transactions
            if t.status
            in (
                BankPaymentTransactionStatus.unmatched,
                BankPaymentTransactionStatus.matched,
            )
        ]
        candidates = suggest_matches(db, record.organization_id, pending)  # type: ignore[invalid-argument-type]
        for tr in reads:
            tr.candidates = candidates.get(tr.id, [])
    read.transactions = reads
    return read


def _load_scoped(
    db: Session, import_id: uuid.UUID, membership: UserOrganizationMembership
) -> BankStatementImport:
    record = BankImportRepository(db).get(import_id)
    if record is None or record.organization_id != membership.organization_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Import not found"
        )
    return record


@router.post("", response_model=BankImportRead, status_code=status.HTTP_201_CREATED)
async def create_bank_import(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(
        require_membership_roles(*_MANAGE_ROLES)
    ),
):
    content = await _read_upload_within_limit(file, _MAX_UPLOAD_BYTES)
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty"
        )
    try:
        entries = parse_camt(content)
    except Iso20022ParseError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    if not entries:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No incoming payments (credit entries) found in the statement",
        )
    storage_url = _store_raw_file(file.filename or "statement.xml", content)
    repo = BankImportRepository(db)
    record = repo.create_import(
        organization_id=membership.organization_id,  # type: ignore[invalid-argument-type]
        file_name=file.filename or "statement.xml",
        storage_url=storage_url,
        entries=entries,
        imported_by_user_id=membership.user_id,  # type: ignore[invalid-argument-type]
    )
    return _to_read(db, record, with_candidates=True)


@router.get("", response_model=list[BankImportListItem])
async def list_bank_imports(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(get_active_membership),
):
    records = BankImportRepository(db).list_for_org(
        membership.organization_id,  # type: ignore[invalid-argument-type]
        skip=skip,
        limit=limit,
    )
    return [BankImportListItem.model_validate(r) for r in records]


@router.get("/{import_id}", response_model=BankImportRead)
async def get_bank_import(
    import_id: uuid.UUID,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(get_active_membership),
):
    record = _load_scoped(db, import_id, membership)
    return _to_read(db, record, with_candidates=True)


@router.post("/{import_id}/apply", response_model=BankImportRead)
async def apply_bank_import(
    import_id: uuid.UUID,
    payload: ApplyImportRequest,
    db: Session = Depends(get_db),
    membership: UserOrganizationMembership = Depends(
        require_membership_roles(*_MANAGE_ROLES)
    ),
):
    record = _load_scoped(db, import_id, membership)
    repo = BankImportRepository(db)
    try:
        updated = repo.apply(
            record,
            assignments=payload.assignments,
            ignore_transaction_ids=payload.ignore_transaction_ids,
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    return _to_read(db, updated, with_candidates=True)
