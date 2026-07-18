"""Inbound-email → document ingestion endpoint.

Mounted in ``app.main`` at ``/email-ingest`` and — like the dev-storage route —
NOT behind the Hanko JWT dependency: the caller is the Cloudflare email-ingest
Worker (a machine), authenticated by a shared-secret header instead of a user
session. See ``app/services/email_ingest.py`` for the resolution rules.
"""

import hmac

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.schemas.email_ingest import EmailIngestRequest, EmailIngestResult
from app.services.email_ingest import EmailIngestService


def require_ingest_token(
    x_email_ingest_token: str = Header(default=""),
) -> None:
    # No token configured ⇒ feature disabled: don't advertise the endpoint.
    if not settings.EMAIL_INGEST_TOKEN:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if not hmac.compare_digest(x_email_ingest_token, settings.EMAIL_INGEST_TOKEN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing or invalid email ingest token",
        )


router = APIRouter(dependencies=[Depends(require_ingest_token)])


@router.post("/documents", response_model=EmailIngestResult)
async def ingest_documents(
    payload: EmailIngestRequest,
    db: Session = Depends(get_db),
) -> EmailIngestResult:
    """Store an inbound email's attachments as documents for the sender's org.

    Always returns 200: a "dropped" result (unknown/ambiguous sender, or nothing
    storable) is a normal outcome, not an error. Only a bad/absent shared-secret
    token is rejected (403/404).
    """
    return await EmailIngestService(db).ingest(payload)
