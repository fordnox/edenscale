"""ISO 20022 bank-statement parsing (camt.053 / camt.052 / camt.054).

Banks deliver received payments as an ISO 20022 XML statement. The three
relevant messages share the same ``Ntry`` (entry) / ``TxDtls`` (transaction
detail) shape, so a single namespace-agnostic walk handles all of them:

* ``camt.053`` — Bank-to-Customer Statement
* ``camt.052`` — Bank-to-Customer Account Report
* ``camt.054`` — Bank-to-Customer Debit/Credit Notification

We only care about **credits** (money arriving, ``CdtDbtInd == CRDT``) since
those are what settle capital calls. Each parsed entry carries the payer name,
amount, value date, remittance text, and a bank reference used for dedupe.

Parsing goes through ``defusedxml`` to neutralise XXE / entity-expansion
attacks in files that arrive from outside the system.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from defusedxml.ElementTree import fromstring

# camt messages whose statement container we recognise. The list is advisory —
# the walk finds ``Ntry`` elements regardless — but it lets us reject files that
# are clearly not a bank statement with a helpful message.
_STATEMENT_CONTAINERS = {
    "BkToCstmrStmt",  # camt.053
    "BkToCstmrAcctRpt",  # camt.052
    "BkToCstmrDbtCdtNtfctn",  # camt.054
}

# Prefix marking a composed (non-bank-issued) fallback reference, used when an
# entry carries no bank reference of its own. Unlike a real bank reference, a
# synthetic key is not proof that two entries are the *same* transaction —
# see the callers in `bank_import_repository.py`, which must not treat a
# matching synthetic reference as evidence a payment already settled.
SYNTHETIC_REFERENCE_PREFIX = "synthetic:"


def is_synthetic_reference(bank_reference: str) -> bool:
    """True if ``bank_reference`` was composed by us, not issued by the bank."""
    return bank_reference.startswith(SYNTHETIC_REFERENCE_PREFIX)


class Iso20022ParseError(ValueError):
    """Raised when the uploaded file is not a parseable camt statement."""


@dataclass
class ParsedBankEntry:
    """One credit transaction extracted from a bank statement."""

    amount: Decimal
    currency: str
    value_date: date | None
    debtor_name: str | None
    debtor_iban: str | None
    remittance_info: str | None
    bank_reference: str


def _local(tag: str) -> str:
    """Strip the ``{namespace}`` prefix ElementTree prepends to every tag."""
    return tag.rsplit("}", 1)[-1]


def _iter(el, name: str):
    """Yield every descendant (any depth) whose local tag name is ``name``."""
    for child in el.iter():
        if _local(child.tag) == name:
            yield child


def _first(el, name: str):
    """First direct or nested descendant with local name ``name`` (or None)."""
    for match in _iter(el, name):
        if match is not el:
            return match
    return None


def _text(el, name: str) -> str | None:
    match = _first(el, name)
    if match is None or match.text is None:
        return None
    text = match.text.strip()
    return text or None


def _child(el, name: str):
    """First *immediate* child with local name ``name`` (or None)."""
    for child in el:
        if _local(child.tag) == name:
            return child
    return None


def _parse_date(el) -> date | None:
    """Read an ISO 20022 date node (``<Dt>`` or ``<DtTm>``) into a ``date``."""
    if el is None:
        return None
    raw = _text(el, "Dt") or _text(el, "DtTm")
    if raw is None:
        return None
    try:
        # ``date.fromisoformat`` accepts ``YYYY-MM-DD``; slice a datetime string
        # down to its date portion so both ``Dt`` and ``DtTm`` parse.
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


def _remittance(scope) -> str | None:
    """Join unstructured remittance lines + any structured creditor reference."""
    rmt = _first(scope, "RmtInf")
    if rmt is None:
        return None
    parts: list[str] = []
    for ustrd in _iter(rmt, "Ustrd"):
        if ustrd.text and ustrd.text.strip():
            parts.append(ustrd.text.strip())
    ref = _text(rmt, "Ref")  # structured CdtrRefInf/Ref
    if ref and ref not in parts:
        parts.append(ref)
    joined = " ".join(parts).strip()
    return joined or None


def _entry_amount(scope) -> tuple[Decimal, str] | None:
    amt_el = _first(scope, "Amt")
    if amt_el is None or amt_el.text is None:
        return None
    try:
        amount = Decimal(amt_el.text.strip())
    except (InvalidOperation, ValueError):
        return None
    currency = (amt_el.get("Ccy") or "").strip().upper()
    return amount, currency


def _extract(
    scope, ntry, value_date: date | None, ordinal: int
) -> ParsedBankEntry | None:
    """Build a credit entry from a ``TxDtls`` (or the ``Ntry`` itself).

    ``scope`` is the element carrying the transaction fields (a ``TxDtls`` when
    present, else the ``Ntry``); ``ntry`` is the enclosing entry used only as a
    fallback for fields banks sometimes place at entry level. ``ordinal`` is
    this entry's position within the statement, used to keep composed
    fallback references distinct — see ``SYNTHETIC_REFERENCE_PREFIX``.
    """
    cdt_dbt = _text(scope, "CdtDbtInd") or _text(ntry, "CdtDbtInd")
    if (cdt_dbt or "").upper() != "CRDT":
        return None  # skip debits — they don't settle capital calls

    amount = _entry_amount(scope) or _entry_amount(ntry)
    if amount is None or amount[0] <= Decimal("0"):
        return None

    # On a credit the counterparty that sent the money is the Debtor.
    related = _first(scope, "RltdPties")
    debtor_name: str | None = None
    debtor_iban: str | None = None
    if related is not None:
        dbtr = _child(related, "Dbtr")
        if dbtr is not None:
            debtor_name = _text(dbtr, "Nm")
        dbtr_acct = _child(related, "DbtrAcct")
        if dbtr_acct is not None:
            debtor_iban = _text(dbtr_acct, "IBAN")

    remittance = _remittance(scope) or _remittance(ntry)

    # Reference for dedupe: prefer a bank-assigned unique id, then end-to-end
    # id, then entry-level refs; fall back to a composed key so re-imports of
    # the same statement still collide. The ordinal is included so two
    # genuinely distinct entries sharing date+amount+payer (e.g. two equal
    # tranches from the same investor) still get distinct keys instead of
    # colliding and silently dropping the second payment.
    reference = (
        _text(scope, "AcctSvcrRef")
        or _text(scope, "EndToEndId")
        or _text(ntry, "AcctSvcrRef")
        or _text(ntry, "NtryRef")
    )
    if not reference:
        reference = (
            f"{SYNTHETIC_REFERENCE_PREFIX}{ordinal}|{value_date}|"
            f"{amount[0]}|{debtor_name or ''}"
        )

    return ParsedBankEntry(
        amount=amount[0],
        currency=amount[1],
        value_date=value_date,
        debtor_name=debtor_name,
        debtor_iban=debtor_iban,
        remittance_info=remittance,
        bank_reference=reference,
    )


def parse_camt(xml_bytes: bytes) -> list[ParsedBankEntry]:
    """Parse a camt.05x statement into its credit entries.

    Raises ``Iso20022ParseError`` when the payload is not valid XML or does not
    look like a bank-to-customer statement.
    """
    try:
        root = fromstring(xml_bytes)
    except Exception as exc:  # defusedxml raises a variety of parse errors
        raise Iso20022ParseError("File is not valid XML") from exc

    containers = {_local(el.tag) for el in root.iter()}
    if not (_STATEMENT_CONTAINERS & containers):
        raise Iso20022ParseError(
            "Not an ISO 20022 bank statement "
            "(expected a camt.053, camt.052 or camt.054 message)"
        )

    entries: list[ParsedBankEntry] = []
    ordinal = 0
    for ntry in _iter(root, "Ntry"):
        value_date = _parse_date(_first(ntry, "ValDt")) or _parse_date(
            _first(ntry, "BookgDt")
        )
        tx_details = [tx for tx in _iter(ntry, "TxDtls") if tx is not ntry]
        scopes = tx_details or [ntry]
        for scope in scopes:
            # Ordinal tracks position within the statement (every scope
            # examined, credit or debit) so it's stable and unambiguous
            # regardless of how many entries turn out to be credits.
            parsed = _extract(scope, ntry, value_date, ordinal)
            ordinal += 1
            if parsed is not None:
                entries.append(parsed)
    return entries
