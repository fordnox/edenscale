import uuid

from sqlalchemy.orm import Session

from app.models.email_ingest_message import EmailIngestMessage


class EmailIngestMessageRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_message_id(self, message_id: str) -> EmailIngestMessage | None:
        return (
            self.db.query(EmailIngestMessage)
            .filter(EmailIngestMessage.message_id == message_id)
            .first()
        )

    def record(
        self,
        *,
        message_id: str,
        document_ids: list[uuid.UUID],
        commit: bool = True,
    ) -> EmailIngestMessage:
        """Add an idempotency row for a processed message.

        ``commit=False`` lets the caller (``EmailIngestService.ingest``) fold
        this write into the same transaction as the ``Document`` rows it
        describes, so the two can never disagree after a crash mid-commit.
        """
        row = EmailIngestMessage(
            message_id=message_id,
            document_ids=[str(document_id) for document_id in document_ids],
        )
        self.db.add(row)
        if commit:
            self.db.commit()
            self.db.refresh(row)
        return row
