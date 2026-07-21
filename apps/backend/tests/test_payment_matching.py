"""Characterization tests for the bank-payment-to-capital-call-item matcher.

These tests pin what ``app.services.payment_matching`` actually does today —
thresholds, weights, tie-breaking, the score floor — so a future change to the
scorer is visible in a diff instead of silently re-ranking which LP's wire is
suggested against which capital-call item.
"""

import uuid
from datetime import date
from decimal import Decimal

import pytest

from app.core.database import Base, SessionLocal, engine
from app.core.slugs import slugify
from app.models import (
    BankPaymentTransaction,
    CapitalCall,
    CapitalCallItem,
    CapitalCallStatus,
    Commitment,
    CommitmentStatus,
    Fund,
    Investor,
    Organization,
    OrganizationType,
)
from app.services.payment_matching import (
    _SCORE_FLOOR,
    _amount_score,
    _confidence,
    _name_score,
    suggest_matches,
)


# ---------------------------------------------------------------------------
# Step 2: pure function unit tests (no DB)
# ---------------------------------------------------------------------------


class TestNameScore:
    def test_exact_match(self):
        assert _name_score("acme lp", "Acme LP", None) == 1.0

    def test_case_insensitive_via_investor_name_normalization(self):
        # _name_score normalizes investor_name/investor_code internally, but
        # NOT its `debtor` argument — suggest_matches always passes an
        # already-normalized (lowercased, whitespace-collapsed) debtor. Tested
        # here the way the real call site uses it: a pre-normalized debtor.
        assert _name_score("acme lp", "ACME LP", None) == 1.0

    def test_debtor_argument_itself_is_not_normalized(self):
        # Documented quirk: if the caller forgot to normalize `debtor`, case
        # differences are NOT absorbed by _name_score itself, only by the
        # investor_name/investor_code side. This is what the code does today.
        mismatched = _name_score("ACME LP", "Acme LP", None)
        normalized = _name_score("acme lp", "Acme LP", None)
        assert normalized == 1.0
        assert mismatched < normalized

    def test_whitespace_and_punctuation_differences(self):
        # investor_name gets whitespace-collapsed by _normalize; punctuation is
        # NOT stripped, so "acme, lp" vs "acme lp" is not a perfect match.
        score = _name_score("acme lp", "Acme,   LP", None)
        assert 0.0 < score < 1.0

    def test_substring_match_scores_partial(self):
        score = _name_score("acme lp fund investments", "Acme LP", None)
        assert 0.0 < score < 1.0

    def test_unrelated_name_scores_low(self):
        score = _name_score("zzz totally unrelated corp", "Acme LP", None)
        assert score < 0.3

    def test_empty_debtor_returns_zero(self):
        assert _name_score("", "Acme LP", None) == 0.0

    def test_none_debtor_returns_zero(self):
        assert _name_score(None, "Acme LP", None) == 0.0  # type: ignore[arg-type]

    def test_investor_code_used_when_better_than_name(self):
        # debtor matches the investor_code exactly but not the name at all.
        score = _name_score("lp-042", "Totally Different Co", "LP-042")
        assert score == 1.0

    def test_investor_code_none_falls_back_to_name_only(self):
        score = _name_score("acme lp", "Acme LP", None)
        assert score == 1.0


class TestAmountScore:
    def test_exact_amount_scores_one(self):
        assert _amount_score(Decimal("1000.00"), Decimal("1000.00")) == Decimal("1")

    def test_slight_underpayment_within_one_percent_scores_085(self):
        # remaining=1000, amount=995 -> abs diff 5 <= 1000*0.01=10
        assert _amount_score(Decimal("995.00"), Decimal("1000.00")) == Decimal("0.85")

    def test_slight_overpayment_within_one_percent_scores_085(self):
        # remaining=1000, amount=1005 -> abs diff 5 <= 10
        assert _amount_score(Decimal("1005.00"), Decimal("1000.00")) == Decimal("0.85")

    def test_exactly_on_one_percent_boundary_scores_085(self):
        # remaining=1000, amount=1010 -> abs diff 10 == 1000*0.01 (<=, inclusive)
        assert _amount_score(Decimal("1010.00"), Decimal("1000.00")) == Decimal("0.85")

    def test_just_outside_one_percent_boundary_overpayment_scores_015(self):
        # remaining=1000, amount=1010.01 -> abs diff 10.01 > 10
        assert _amount_score(Decimal("1010.01"), Decimal("1000.00")) == Decimal("0.15")

    def test_gross_underpayment_scores_05_plausible_partial(self):
        assert _amount_score(Decimal("500.00"), Decimal("1000.00")) == Decimal("0.5")

    def test_gross_overpayment_scores_015(self):
        assert _amount_score(Decimal("1500.00"), Decimal("1000.00")) == Decimal("0.15")

    def test_zero_amount_against_open_balance_scores_05(self):
        # A $0 credit is treated the same as any other underpayment: "plausible
        # partial payment" at 0.5. This looks odd (a zero-value transaction
        # should probably never be a plausible partial payment) but it is what
        # the code does today — see report.
        assert _amount_score(Decimal("0"), Decimal("1000.00")) == Decimal("0.5")

    def test_remaining_zero_scores_zero_regardless_of_amount(self):
        assert _amount_score(Decimal("1000.00"), Decimal("0")) == Decimal("0")

    def test_remaining_negative_scores_zero(self):
        assert _amount_score(Decimal("1000.00"), Decimal("-50.00")) == Decimal("0")


class TestConfidence:
    @pytest.mark.parametrize(
        "score,expected",
        [
            (0.0, "low"),
            (0.44, "low"),
            (0.45, "medium"),  # boundary: exactly on the medium threshold
            (0.46, "medium"),
            (0.74, "medium"),
            (0.75, "high"),  # boundary: exactly on the high threshold
            (0.76, "high"),
            (1.0, "high"),
        ],
    )
    def test_confidence_thresholds(self, score, expected):
        assert _confidence(score) == expected


# ---------------------------------------------------------------------------
# Step 3: suggest_matches ordering, floor, and status filtering (DB-backed)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def _mk_org(db, name: str = "Matching Org") -> Organization:
    org = Organization(
        name=name, slug=slugify(name), type=OrganizationType.fund_manager_firm
    )
    db.add(org)
    db.flush()
    return org


def _mk_fund(db, org: Organization, name: str = "Fund X", currency: str = "USD") -> Fund:
    fund = Fund(
        organization_id=org.id,
        name=name,
        slug=slugify(name) + "-" + uuid.uuid4().hex[:6],
        currency_code=currency,
    )
    db.add(fund)
    db.flush()
    return fund


def _mk_investor(db, org: Organization, name: str, code: str | None = None) -> Investor:
    investor = Investor(organization_id=org.id, name=name, investor_code=code)
    db.add(investor)
    db.flush()
    return investor


def _mk_commitment(db, fund: Fund, investor: Investor, amount: str = "100000.00") -> Commitment:
    commitment = Commitment(
        fund_id=fund.id,
        investor_id=investor.id,
        committed_amount=Decimal(amount),
        commitment_date=date(2026, 1, 1),
        status=CommitmentStatus.approved,
    )
    db.add(commitment)
    db.flush()
    return commitment


def _mk_call(
    db, fund: Fund, status: CapitalCallStatus, title: str = "Call", amount: str = "1000.00"
) -> CapitalCall:
    call = CapitalCall(
        fund_id=fund.id,
        title=title,
        due_date=date(2026, 6, 1),
        amount=Decimal(amount),
        status=status,
    )
    db.add(call)
    db.flush()
    return call


def _mk_item(
    db,
    call: CapitalCall,
    commitment: Commitment,
    amount_due: str = "1000.00",
    amount_paid: str = "0",
) -> CapitalCallItem:
    item = CapitalCallItem(
        capital_call_id=call.id,
        commitment_id=commitment.id,
        amount_due=Decimal(amount_due),
        amount_paid=Decimal(amount_paid),
    )
    db.add(item)
    db.flush()
    return item


def _mk_txn(
    amount: str,
    debtor_name: str = "",
    remittance_info: str = "",
    currency: str = "USD",
) -> BankPaymentTransaction:
    """An in-memory (never persisted) transaction — suggest_matches only reads
    attributes off these, it never queries them from the DB."""
    return BankPaymentTransaction(
        id=uuid.uuid4(),
        import_id=uuid.uuid4(),
        amount=Decimal(amount),
        currency=currency,
        debtor_name=debtor_name,
        remittance_info=remittance_info,
        bank_reference=f"REF-{uuid.uuid4().hex[:8]}",
    )


class TestSuggestMatchesOrdering:
    def test_candidates_come_back_in_descending_score_order(self):
        db = SessionLocal()
        try:
            org = _mk_org(db)
            fund = _mk_fund(db, org)

            # A: exact amount + exact name -> top score.
            inv_a = _mk_investor(db, org, "Acme LP")
            commit_a = _mk_commitment(db, fund, inv_a)
            call_a = _mk_call(db, fund, CapitalCallStatus.sent, title="Call A")
            item_a = _mk_item(db, call_a, commit_a, amount_due="1000.00")

            # B: exact amount but unrelated name -> lower score than A.
            inv_b = _mk_investor(db, org, "Zephyr Holdings")
            commit_b = _mk_commitment(db, fund, inv_b)
            call_b = _mk_call(db, fund, CapitalCallStatus.sent, title="Call B")
            item_b = _mk_item(db, call_b, commit_b, amount_due="1000.00")

            # C: gross overpayment (amount_due=100, txn pays 1000) and an
            # unrelated name -> amount_score 0.15, name_score ~0.19; verified
            # combined total (~0.14) falls under _SCORE_FLOOR, so C should not
            # appear in the results at all.
            inv_c = _mk_investor(db, org, "Nadir Partners")
            commit_c = _mk_commitment(db, fund, inv_c)
            call_c = _mk_call(db, fund, CapitalCallStatus.sent, title="Call C")
            item_c = _mk_item(db, call_c, commit_c, amount_due="100.00")

            db.commit()

            txn = _mk_txn("1000.00", debtor_name="Acme LP")
            results = suggest_matches(db, org.id, [txn])
            candidates = results[txn.id]

            scores = [c.score for c in candidates]
            assert scores == sorted(scores, reverse=True)
            ids = [c.capital_call_item_id for c in candidates]
            assert ids[0] == item_a.id
            assert item_b.id in ids
            assert item_c.id not in ids
        finally:
            db.close()

    def test_candidate_below_score_floor_is_not_suggested(self):
        db = SessionLocal()
        try:
            org = _mk_org(db)
            fund = _mk_fund(db, org)
            investor = _mk_investor(db, org, "Bexley Woodcraft Partners")
            commitment = _mk_commitment(db, fund, investor)
            call = _mk_call(db, fund, CapitalCallStatus.sent, amount="100.00")
            # Overpayment beyond the 1% band -> amount_score 0.15 (weighted
            # 0.075) and an unrelated debtor name -> name_score ~0.196
            # (weighted ~0.069), no reference hit. Verified combined total
            # ~0.144, comfortably under _SCORE_FLOOR (0.2).
            _mk_item(db, call, commitment, amount_due="100.00")
            db.commit()
            assert float(_SCORE_FLOOR) == 0.2

            txn = _mk_txn("1000.00", debtor_name="Quantum Fisheries Holdings")
            results = suggest_matches(db, org.id, [txn])
            assert results[txn.id] == []
        finally:
            db.close()

    def test_paid_call_item_is_not_offered(self):
        db = SessionLocal()
        try:
            org = _mk_org(db)
            fund = _mk_fund(db, org)
            investor = _mk_investor(db, org, "Acme LP")
            commitment = _mk_commitment(db, fund, investor)
            call = _mk_call(db, fund, CapitalCallStatus.paid)
            _mk_item(db, call, commitment, amount_due="1000.00", amount_paid="1000.00")
            db.commit()

            txn = _mk_txn("1000.00", debtor_name="Acme LP")
            results = suggest_matches(db, org.id, [txn])
            assert results[txn.id] == []
        finally:
            db.close()

    def test_cancelled_call_item_is_not_offered(self):
        db = SessionLocal()
        try:
            org = _mk_org(db)
            fund = _mk_fund(db, org)
            investor = _mk_investor(db, org, "Acme LP")
            commitment = _mk_commitment(db, fund, investor)
            call = _mk_call(db, fund, CapitalCallStatus.cancelled)
            _mk_item(db, call, commitment, amount_due="1000.00")
            db.commit()

            txn = _mk_txn("1000.00", debtor_name="Acme LP")
            results = suggest_matches(db, org.id, [txn])
            assert results[txn.id] == []
        finally:
            db.close()

    def test_overdue_call_item_is_offered(self):
        # Pins the behavior noted in plan 005: an overdue call is still a
        # valid match target even though the dashboard may treat "overdue"
        # differently elsewhere.
        db = SessionLocal()
        try:
            org = _mk_org(db)
            fund = _mk_fund(db, org)
            investor = _mk_investor(db, org, "Acme LP")
            commitment = _mk_commitment(db, fund, investor)
            call = _mk_call(db, fund, CapitalCallStatus.overdue)
            item = _mk_item(db, call, commitment, amount_due="1000.00")
            db.commit()

            txn = _mk_txn("1000.00", debtor_name="Acme LP")
            results = suggest_matches(db, org.id, [txn])
            ids = [c.capital_call_item_id for c in results[txn.id]]
            assert item.id in ids
        finally:
            db.close()

    def test_draft_and_scheduled_calls_are_not_offered(self):
        db = SessionLocal()
        try:
            org = _mk_org(db)
            fund = _mk_fund(db, org)
            for status in (CapitalCallStatus.draft, CapitalCallStatus.scheduled):
                investor = _mk_investor(db, org, f"Acme LP {status.value}")
                commitment = _mk_commitment(db, fund, investor)
                call = _mk_call(db, fund, status, title=f"Call {status.value}")
                _mk_item(db, call, commitment, amount_due="1000.00")
            db.commit()

            txn = _mk_txn("1000.00", debtor_name="Acme LP")
            results = suggest_matches(db, org.id, [txn])
            assert results[txn.id] == []
        finally:
            db.close()

    def test_tie_breaking_is_deterministic_across_runs(self):
        # Two candidates with identical amount/name/reference signals score
        # identically. Python's list.sort() is stable, so ties keep the order
        # the rows came back from the query — pin that this is reproducible
        # across repeated calls, not merely "some" order.
        db = SessionLocal()
        try:
            org = _mk_org(db)
            fund = _mk_fund(db, org)

            inv_1 = _mk_investor(db, org, "Twin Capital", code="TW-1")
            commit_1 = _mk_commitment(db, fund, inv_1)
            call_1 = _mk_call(db, fund, CapitalCallStatus.sent, title="Call Twin 1")
            item_1 = _mk_item(db, call_1, commit_1, amount_due="1000.00")

            inv_2 = _mk_investor(db, org, "Twin Capital", code="TW-2")
            commit_2 = _mk_commitment(db, fund, inv_2)
            call_2 = _mk_call(db, fund, CapitalCallStatus.sent, title="Call Twin 2")
            item_2 = _mk_item(db, call_2, commit_2, amount_due="1000.00")

            db.commit()

            txn = _mk_txn("1000.00", debtor_name="Twin Capital")
            first_run = [c.capital_call_item_id for c in suggest_matches(db, org.id, [txn])[txn.id]]
            second_run = [c.capital_call_item_id for c in suggest_matches(db, org.id, [txn])[txn.id]]

            assert first_run == second_run
            assert set(first_run) == {item_1.id, item_2.id}
        finally:
            db.close()

    def test_currency_mismatch_flag_set_when_txn_currency_differs(self):
        db = SessionLocal()
        try:
            org = _mk_org(db)
            fund = _mk_fund(db, org, currency="EUR")
            investor = _mk_investor(db, org, "Acme LP")
            commitment = _mk_commitment(db, fund, investor)
            call = _mk_call(db, fund, CapitalCallStatus.sent)
            _mk_item(db, call, commitment, amount_due="1000.00")
            db.commit()

            txn = _mk_txn("1000.00", debtor_name="Acme LP", currency="USD")
            results = suggest_matches(db, org.id, [txn])
            assert results[txn.id][0].currency_mismatch is True
        finally:
            db.close()

    def test_org_scoping_excludes_other_orgs_items(self):
        db = SessionLocal()
        try:
            org_a = _mk_org(db, "Org A")
            org_b = _mk_org(db, "Org B")
            fund_b = _mk_fund(db, org_b)
            investor_b = _mk_investor(db, org_b, "Acme LP")
            commitment_b = _mk_commitment(db, fund_b, investor_b)
            call_b = _mk_call(db, fund_b, CapitalCallStatus.sent)
            _mk_item(db, call_b, commitment_b, amount_due="1000.00")
            db.commit()

            txn = _mk_txn("1000.00", debtor_name="Acme LP")
            results = suggest_matches(db, org_a.id, [txn])
            assert results[txn.id] == []
        finally:
            db.close()
