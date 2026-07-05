"""Suggest which open capital-call item each imported bank payment settles.

There is no bank-account identifier on investors, so matching leans on three
signals with no single source of truth:

* **amount** — does the credit equal (or fit within) the item's outstanding
  balance? Strongest signal.
* **payer name** — fuzzy similarity between the statement's debtor name and the
  investor's name / code (``difflib.SequenceMatcher``).
* **remittance reference** — does the free-text reference mention the investor
  code, investor name, or the capital-call title?

Each candidate gets a 0–1 score and a coarse confidence tier the wizard shows
next to a pre-selected match. The manager always confirms before anything is
written, so a wrong-but-plausible suggestion is a nudge, never an action.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from difflib import SequenceMatcher

from sqlalchemy.orm import Session

from app.models.bank_payment_transaction import BankPaymentTransaction
from app.models.capital_call import CapitalCall
from app.models.capital_call_item import CapitalCallItem
from app.models.commitment import Commitment
from app.models.enums import CapitalCallStatus
from app.models.fund import Fund
from app.models.investor import Investor
from app.schemas.bank_import import Confidence, MatchCandidate

# Only calls that are actually out for collection make sensible targets.
_COLLECTIBLE_STATUSES = (
    CapitalCallStatus.sent,
    CapitalCallStatus.partially_paid,
    CapitalCallStatus.overdue,
)

_MAX_CANDIDATES = 5
# Drop candidates below this so a statement line with no plausible target shows
# an empty suggestion list rather than five noise rows.
_SCORE_FLOOR = 0.2

_WEIGHT_AMOUNT = Decimal("0.5")
_WEIGHT_NAME = 0.35
_WEIGHT_REFERENCE = 0.15


def _normalize(value: str | None) -> str:
    return " ".join((value or "").lower().split())


def _name_score(debtor: str, investor_name: str, investor_code: str | None) -> float:
    if not debtor:
        return 0.0
    best = SequenceMatcher(None, debtor, _normalize(investor_name)).ratio()
    if investor_code:
        best = max(
            best, SequenceMatcher(None, debtor, _normalize(investor_code)).ratio()
        )
    return best


def _reference_hit(
    remittance: str, investor_name: str, investor_code: str | None, call_title: str
) -> bool:
    if not remittance:
        return False
    if investor_code and _normalize(investor_code) in remittance:
        return True
    if call_title and _normalize(call_title) in remittance:
        return True
    # Any investor-name token of length >= 4 appearing in the reference counts.
    tokens = [tok for tok in _normalize(investor_name).split() if len(tok) >= 4]
    return any(tok in remittance for tok in tokens)


def _amount_score(amount: Decimal, remaining: Decimal) -> Decimal:
    if remaining <= Decimal("0"):
        return Decimal("0")
    if amount == remaining:
        return Decimal("1")
    # Within 1% of the outstanding balance — treat as an intended full payment.
    if abs(amount - remaining) <= (remaining * Decimal("0.01")):
        return Decimal("0.85")
    if amount < remaining:
        return Decimal("0.5")  # plausible partial payment
    return Decimal("0.15")  # overpayment — unlikely but not impossible


def _confidence(score: float) -> Confidence:
    if score >= 0.75:
        return "high"
    if score >= 0.45:
        return "medium"
    return "low"


def _open_items(db: Session, organization_id: uuid.UUID):
    """Open capital-call items (remaining > 0) on collectible calls in the org."""
    return (
        db.query(CapitalCallItem, CapitalCall, Commitment, Investor, Fund)
        .join(CapitalCall, CapitalCall.id == CapitalCallItem.capital_call_id)
        .join(Commitment, Commitment.id == CapitalCallItem.commitment_id)
        .join(Investor, Investor.id == Commitment.investor_id)
        .join(Fund, Fund.id == CapitalCall.fund_id)
        .filter(
            Fund.organization_id == organization_id,
            CapitalCall.status.in_(_COLLECTIBLE_STATUSES),
            CapitalCallItem.amount_paid < CapitalCallItem.amount_due,
        )
        .all()
    )


def suggest_matches(
    db: Session,
    organization_id: uuid.UUID,
    transactions: list[BankPaymentTransaction],
) -> dict[uuid.UUID, list[MatchCandidate]]:
    """Return, per transaction id, its ranked list of candidate items."""
    rows = _open_items(db, organization_id)
    results: dict[uuid.UUID, list[MatchCandidate]] = {}

    for txn in transactions:
        debtor = _normalize(txn.debtor_name)  # type: ignore[invalid-argument-type]
        remittance = _normalize(txn.remittance_info)  # type: ignore[invalid-argument-type]
        txn_currency = (txn.currency or "").upper()
        scored: list[MatchCandidate] = []

        for item, call, _commitment, investor, fund in rows:
            remaining = Decimal(item.amount_due) - Decimal(item.amount_paid)
            amount_score = _amount_score(Decimal(txn.amount), remaining)  # type: ignore[invalid-argument-type]
            name_score = _name_score(debtor, investor.name, investor.investor_code)
            ref_hit = _reference_hit(
                remittance, investor.name, investor.investor_code, call.title
            )
            score = (
                float(_WEIGHT_AMOUNT * amount_score)
                + _WEIGHT_NAME * name_score
                + (_WEIGHT_REFERENCE if ref_hit else 0.0)
            )
            if score < _SCORE_FLOOR:
                continue
            scored.append(
                MatchCandidate(
                    capital_call_item_id=item.id,
                    capital_call_id=call.id,
                    capital_call_title=call.title,
                    fund_id=fund.id,
                    fund_name=fund.name,
                    currency_code=fund.currency_code,
                    investor_id=investor.id,
                    investor_name=investor.name,
                    amount_due=Decimal(item.amount_due),
                    amount_paid=Decimal(item.amount_paid),
                    remaining=remaining,
                    score=round(score, 4),
                    confidence=_confidence(score),
                    currency_mismatch=bool(
                        txn_currency and txn_currency != fund.currency_code.upper()
                    ),
                )
            )

        scored.sort(key=lambda c: c.score, reverse=True)
        results[txn.id] = scored[:_MAX_CANDIDATES]  # type: ignore[invalid-assignment]

    return results
