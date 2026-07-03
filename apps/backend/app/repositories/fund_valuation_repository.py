import uuid

from sqlalchemy.orm import Session

from app.models.fund_valuation import FundValuation
from app.schemas.fund_valuation import FundValuationCreate


class FundValuationRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_for_fund(self, fund_id: uuid.UUID) -> list[FundValuation]:
        return (
            self.db.query(FundValuation)
            .filter(FundValuation.fund_id == fund_id)
            .order_by(FundValuation.as_of_date.desc())
            .all()
        )

    def get(self, valuation_id: uuid.UUID) -> FundValuation | None:
        return (
            self.db.query(FundValuation)
            .filter(FundValuation.id == valuation_id)
            .first()
        )

    def upsert(
        self,
        *,
        fund_id: uuid.UUID,
        data: FundValuationCreate,
        created_by_user_id: uuid.UUID | None,
    ) -> FundValuation:
        """Create a valuation, or overwrite the NAV/note if one already exists
        for the same (fund, as_of_date) — one mark per date."""
        existing = (
            self.db.query(FundValuation)
            .filter(
                FundValuation.fund_id == fund_id,
                FundValuation.as_of_date == data.as_of_date,
            )
            .first()
        )
        if existing is not None:
            existing.nav = data.nav
            existing.note = data.note
            self.db.commit()
            self.db.refresh(existing)
            return existing
        valuation = FundValuation(
            fund_id=fund_id,
            as_of_date=data.as_of_date,
            nav=data.nav,
            note=data.note,
            created_by_user_id=created_by_user_id,
        )
        self.db.add(valuation)
        self.db.commit()
        self.db.refresh(valuation)
        return valuation

    def delete(self, valuation_id: uuid.UUID) -> bool:
        valuation = self.get(valuation_id)
        if valuation is None:
            return False
        self.db.delete(valuation)
        self.db.commit()
        return True
