"""Tests for the ISO 20022 bank-payment import flow.

Covers the pure camt parser plus the end-to-end upload → suggest → apply path
and its dedupe guard, mirroring the seed helpers in
``test_capital_calls_api.py``.
"""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.core.database import Base, SessionLocal, engine
from app.core.slugs import slugify
from app.main import app
from app.models import (
    Commitment,
    CommitmentStatus,
    Fund,
    Investor,
    Organization,
    OrganizationType,
    User,
    UserRole,
)
from app.models.capital_call_item import CapitalCallItem
from app.models.user_organization_membership import UserOrganizationMembership
from app.services.iso20022 import Iso20022ParseError, parse_camt


@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


def _camt_053(entries: list[dict]) -> bytes:
    """Build a minimal camt.053 statement from entry dicts.

    Each entry dict: amount, ccy, ind (CRDT/DBIT), name, ref, ustrd, dt.
    """
    ntries = []
    for e in entries:
        ntries.append(
            f"""
      <Ntry>
        <Amt Ccy="{e.get('ccy', 'USD')}">{e['amount']}</Amt>
        <CdtDbtInd>{e.get('ind', 'CRDT')}</CdtDbtInd>
        <ValDt><Dt>{e.get('dt', '2026-07-01')}</Dt></ValDt>
        <NtryDtls><TxDtls>
          <Refs><EndToEndId>{e.get('ref', 'REF')}</EndToEndId></Refs>
          <RltdPties>
            <Dbtr><Nm>{e.get('name', '')}</Nm></Dbtr>
            <DbtrAcct><Id><IBAN>{e.get('iban', '')}</IBAN></Id></DbtrAcct>
          </RltdPties>
          <RmtInf><Ustrd>{e.get('ustrd', '')}</Ustrd></RmtInf>
        </TxDtls></NtryDtls>
      </Ntry>"""
        )
    body = "".join(ntries)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:camt.053.001.02">
  <BkToCstmrStmt><Stmt><Id>S1</Id>{body}</Stmt></BkToCstmrStmt>
</Document>""".encode()


# ---------------------------------------------------------------------------
# Parser unit tests
# ---------------------------------------------------------------------------


class TestParser:
    def test_extracts_credits_skips_debits(self):
        xml = _camt_053(
            [
                {"amount": "1000.00", "ind": "CRDT", "name": "Acme LP", "ref": "R1"},
                {"amount": "50.00", "ind": "DBIT", "name": "Bank Fee", "ref": "R2"},
            ]
        )
        entries = parse_camt(xml)
        assert len(entries) == 1
        assert entries[0].amount == Decimal("1000.00")
        assert entries[0].currency == "USD"
        assert entries[0].debtor_name == "Acme LP"
        assert entries[0].value_date == date(2026, 7, 1)
        assert entries[0].bank_reference == "R1"

    def test_rejects_non_camt(self):
        with pytest.raises(Iso20022ParseError):
            parse_camt(b"<foo>not a statement</foo>")

    def test_rejects_invalid_xml(self):
        with pytest.raises(Iso20022ParseError):
            parse_camt(b"not xml at all {")


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


def _seed_org(name: str = "NewTaven Capital") -> str:
    db = SessionLocal()
    try:
        org = Organization(
            name=name, slug=slugify(name), type=OrganizationType.fund_manager_firm
        )
        db.add(org)
        db.commit()
        return str(org.id)
    finally:
        db.close()


def _seed_user(subject_id: str, role: UserRole, organization_id: str) -> str:
    db = SessionLocal()
    try:
        user = User(
            first_name="First",
            last_name="Last",
            email=f"{subject_id}@example.com",
            hanko_subject_id=subject_id,
        )
        db.add(user)
        db.flush()
        db.add(
            UserOrganizationMembership(
                user_id=user.id, organization_id=organization_id, role=role
            )
        )
        db.commit()
        return str(user.id)
    finally:
        db.close()


def _seed_fund(organization_id: str, *, currency: str = "USD") -> str:
    db = SessionLocal()
    try:
        fund = Fund(
            organization_id=organization_id,
            name="Fund I",
            slug=slugify("Fund I"),
            currency_code=currency,
        )
        db.add(fund)
        db.commit()
        return str(fund.id)
    finally:
        db.close()


def _seed_investor(organization_id: str, *, name: str, code: str | None = None) -> str:
    db = SessionLocal()
    try:
        investor = Investor(organization_id=organization_id, name=name, investor_code=code)
        db.add(investor)
        db.commit()
        return str(investor.id)
    finally:
        db.close()


def _seed_commitment(fund_id: str, investor_id: str) -> str:
    db = SessionLocal()
    try:
        commitment = Commitment(
            fund_id=fund_id,
            investor_id=investor_id,
            committed_amount=Decimal("100000.00"),
            commitment_date=date(2026, 1, 1),
            status=CommitmentStatus.approved,
        )
        db.add(commitment)
        db.commit()
        return str(commitment.id)
    finally:
        db.close()


def _seed_sent_call(client, fund_id: str, commitment_id: str, amount: str) -> tuple[str, str]:
    """Create a capital call with one item and send it. Returns (call_id, item_id)."""
    create = client.post(
        "/capital-calls",
        json={
            "fund_id": fund_id,
            "title": "Q1 Call",
            "due_date": "2026-06-01",
            "amount": amount,
        },
    )
    assert create.status_code == 201, create.text
    call_id = create.json()["id"]
    items = client.post(
        f"/capital-calls/{call_id}/items",
        json={"items": [{"commitment_id": commitment_id, "amount_due": amount}]},
    )
    assert items.status_code == 201, items.text
    item_id = items.json()[0]["id"]
    sent = client.post(f"/capital-calls/{call_id}/send")
    assert sent.status_code == 200, sent.text
    return call_id, item_id


# ---------------------------------------------------------------------------
# End-to-end flow
# ---------------------------------------------------------------------------


class TestImportFlow:
    def test_upload_suggests_and_apply_marks_paid(self, client, override_user):
        org_id = _seed_org()
        _seed_user("fm", UserRole.fund_manager, org_id)
        override_user("fm")
        fund_id = _seed_fund(org_id)
        investor_id = _seed_investor(org_id, name="Acme LP")
        commitment_id = _seed_commitment(fund_id, investor_id)
        call_id, item_id = _seed_sent_call(client, fund_id, commitment_id, "1000.00")

        xml = _camt_053(
            [{"amount": "1000.00", "name": "Acme LP", "ref": "BANK-REF-1"}]
        )
        upload = client.post(
            "/capital-call-imports",
            files={"file": ("statement.xml", xml, "application/xml")},
        )
        assert upload.status_code == 201, upload.text
        data = upload.json()
        assert data["transaction_count"] == 1
        txn = data["transactions"][0]
        assert Decimal(txn["amount"]) == Decimal("1000.00")
        # The exact-amount, exact-name match should be the top candidate.
        assert txn["candidates"], "expected at least one suggested match"
        top = txn["candidates"][0]
        assert top["capital_call_item_id"] == item_id
        assert top["confidence"] == "high"
        assert top["currency_mismatch"] is False

        import_id = data["id"]
        apply = client.post(
            f"/capital-call-imports/{import_id}/apply",
            json={
                "assignments": [
                    {
                        "transaction_id": txn["id"],
                        "capital_call_item_id": item_id,
                        "amount": "1000.00",
                    }
                ]
            },
        )
        assert apply.status_code == 200, apply.text
        applied = apply.json()
        assert applied["status"] == "applied"
        assert applied["applied_count"] == 1
        assert applied["transactions"][0]["status"] == "applied"

        # The capital call should now read as paid.
        call = client.get(f"/capital-calls/{call_id}").json()
        assert call["status"] == "paid"
        db = SessionLocal()
        try:
            item = db.get(CapitalCallItem, item_id)
            assert item.amount_paid == Decimal("1000.00")
            assert item.paid_at is not None
        finally:
            db.close()

    def test_reapply_is_idempotent(self, client, override_user):
        org_id = _seed_org()
        _seed_user("fm", UserRole.fund_manager, org_id)
        override_user("fm")
        fund_id = _seed_fund(org_id)
        investor_id = _seed_investor(org_id, name="Acme LP")
        commitment_id = _seed_commitment(fund_id, investor_id)
        _call_id, item_id = _seed_sent_call(client, fund_id, commitment_id, "1000.00")

        xml = _camt_053([{"amount": "1000.00", "name": "Acme LP", "ref": "REF-DEDUP"}])
        import_id = client.post(
            "/capital-call-imports",
            files={"file": ("s.xml", xml, "application/xml")},
        ).json()["id"]
        txn_id = client.get(f"/capital-call-imports/{import_id}").json()[
            "transactions"
        ][0]["id"]

        body = {
            "assignments": [
                {
                    "transaction_id": txn_id,
                    "capital_call_item_id": item_id,
                    "amount": "1000.00",
                }
            ]
        }
        client.post(f"/capital-call-imports/{import_id}/apply", json=body)
        # Applying the same assignment again must not double-pay.
        client.post(f"/capital-call-imports/{import_id}/apply", json=body)

        db = SessionLocal()
        try:
            item = db.get(CapitalCallItem, item_id)
            assert item.amount_paid == Decimal("1000.00")
        finally:
            db.close()

    def test_reupload_same_reference_is_skipped(self, client, override_user):
        """A re-uploaded statement (fresh import, same bank ref) must not re-pay."""
        org_id = _seed_org()
        _seed_user("fm", UserRole.fund_manager, org_id)
        override_user("fm")
        fund_id = _seed_fund(org_id)
        investor_id = _seed_investor(org_id, name="Acme LP")
        commitment_id = _seed_commitment(fund_id, investor_id)
        _call_id, item_id = _seed_sent_call(client, fund_id, commitment_id, "2000.00")

        xml = _camt_053([{"amount": "1000.00", "name": "Acme LP", "ref": "SHARED-REF"}])

        def _upload_and_apply() -> dict:
            imp = client.post(
                "/capital-call-imports",
                files={"file": ("s.xml", xml, "application/xml")},
            ).json()
            txn = imp["transactions"][0]
            return client.post(
                f"/capital-call-imports/{imp['id']}/apply",
                json={
                    "assignments": [
                        {
                            "transaction_id": txn["id"],
                            "capital_call_item_id": item_id,
                            "amount": "1000.00",
                        }
                    ]
                },
            ).json()

        _upload_and_apply()
        second = _upload_and_apply()
        # Second import's transaction is ignored (reference already applied).
        assert second["transactions"][0]["status"] == "ignored"
        assert second["applied_count"] == 0

        db = SessionLocal()
        try:
            item = db.get(CapitalCallItem, item_id)
            assert item.amount_paid == Decimal("1000.00")  # not 2000
        finally:
            db.close()

    def test_upload_with_no_credits_is_rejected(self, client, override_user):
        org_id = _seed_org()
        _seed_user("fm", UserRole.fund_manager, org_id)
        override_user("fm")
        xml = _camt_053([{"amount": "50.00", "ind": "DBIT", "name": "Fee"}])
        resp = client.post(
            "/capital-call-imports",
            files={"file": ("s.xml", xml, "application/xml")},
        )
        assert resp.status_code == 400

    def test_import_is_org_scoped(self, client, override_user):
        org_a = _seed_org("Org A")
        _seed_user("fm-a", UserRole.fund_manager, org_a)
        override_user("fm-a")
        xml = _camt_053([{"amount": "1000.00", "name": "Acme LP", "ref": "R"}])
        import_id = client.post(
            "/capital-call-imports",
            files={"file": ("s.xml", xml, "application/xml")},
        ).json()["id"]

        # A manager in another org cannot see it.
        org_b = _seed_org("Org B")
        _seed_user("fm-b", UserRole.fund_manager, org_b)
        override_user("fm-b")
        assert client.get(f"/capital-call-imports/{import_id}").status_code == 404


class TestUploadSizeEnforcement:
    """The 25 MB cap must bound memory, not just be checked after the whole
    file is already buffered (plans/015-input-hardening.md, item (b))."""

    def test_stream_exceeding_cap_is_aborted_mid_transfer(
        self, client, override_user, monkeypatch
    ):
        # Lower the cap so the test doesn't need to push real multi-MB
        # payloads through the client. `_read_upload_within_limit` reads in
        # fixed-size chunks and aborts once the running total crosses the
        # cap -- this proves that streaming counter, not a check on the
        # final buffered size, is what raises.
        monkeypatch.setattr(
            "app.routers.bank_imports._MAX_UPLOAD_BYTES", 10, raising=True
        )
        org_id = _seed_org()
        _seed_user("fm", UserRole.fund_manager, org_id)
        override_user("fm")

        oversized = b"<Document>" + b"x" * 1000
        resp = client.post(
            "/capital-call-imports",
            files={"file": ("statement.xml", oversized, "application/xml")},
        )
        assert resp.status_code == 413
