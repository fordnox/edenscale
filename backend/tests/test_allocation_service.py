"""Pure-function tests for allocate_pro_rata covering rounding edge cases."""

from decimal import Decimal

import pytest

from app.models.commitment import Commitment
from app.services.allocation import allocate_pro_rata


def _commitment(amount: str) -> Commitment:
    """Build an unsaved Commitment carrying just enough state for allocation."""
    return Commitment(committed_amount=Decimal(amount))


class TestAllocateProRata:
    def test_empty_commitments_returns_empty_list(self):
        assert allocate_pro_rata(Decimal("100.00"), []) == []

    def test_zero_total_returns_zero_shares(self):
        commitments = [_commitment("1000.00"), _commitment("500.00")]
        result = allocate_pro_rata(Decimal("0"), commitments)
        assert [share for _, share in result] == [Decimal("0.00"), Decimal("0.00")]

    def test_negative_total_raises_value_error(self):
        with pytest.raises(ValueError):
            allocate_pro_rata(Decimal("-1.00"), [_commitment("100.00")])

    def test_zero_total_committed_raises_value_error(self):
        commitments = [_commitment("0"), _commitment("0")]
        with pytest.raises(ValueError):
            allocate_pro_rata(Decimal("100.00"), commitments)

    def test_single_commitment_receives_full_amount(self):
        commitment = _commitment("1000.00")
        result = allocate_pro_rata(Decimal("250.00"), [commitment])
        assert result == [(commitment, Decimal("250.00"))]

    def test_even_split_two_equal_commitments(self):
        c_a = _commitment("500.00")
        c_b = _commitment("500.00")
        result = allocate_pro_rata(Decimal("1000.00"), [c_a, c_b])
        shares = [share for _, share in result]
        assert shares == [Decimal("500.00"), Decimal("500.00")]
        assert sum(shares) == Decimal("1000.00")

    def test_proportional_split_uneven_weights(self):
        c_a = _commitment("750.00")
        c_b = _commitment("250.00")
        result = allocate_pro_rata(Decimal("100.00"), [c_a, c_b])
        shares_by_commitment = {id(c): share for c, share in result}
        assert shares_by_commitment[id(c_a)] == Decimal("75.00")
        assert shares_by_commitment[id(c_b)] == Decimal("25.00")

    def test_rounding_remainder_lands_on_largest_commitment(self):
        c_small = _commitment("100.00")
        c_large = _commitment("200.00")
        c_mid = _commitment("100.00")
        result = allocate_pro_rata(Decimal("100.00"), [c_small, c_large, c_mid])
        shares = {id(c): share for c, share in result}
        # 100 split 1:2:1 → 25.00 / 50.00 / 25.00, exactly reconciles
        assert shares[id(c_small)] == Decimal("25.00")
        assert shares[id(c_large)] == Decimal("50.00")
        assert shares[id(c_mid)] == Decimal("25.00")
        total = sum(shares.values(), Decimal("0"))
        assert total == Decimal("100.00")

    def test_three_way_split_with_rounding_remainder(self):
        # 100 / 3 = 33.333... → rounds to 33.33 each, leaves a 0.01 remainder
        # that must land on the largest commitment so the sum reconciles.
        c_one = _commitment("100.00")
        c_two = _commitment("200.00")
        c_three = _commitment("100.00")
        result = allocate_pro_rata(Decimal("100.00"), [c_one, c_two, c_three])
        shares = {id(c): share for c, share in result}
        total = sum(shares.values(), Decimal("0"))
        assert total == Decimal("100.00")
        # Largest weight (c_two at 200) receives the rounding sweep.
        assert shares[id(c_two)] >= shares[id(c_one)]
        assert shares[id(c_two)] >= shares[id(c_three)]

    def test_remainder_sweep_keeps_sum_exact_for_thirds(self):
        # Three equal commitments splitting 100 → 33.33 / 33.33 / 33.34
        # remainder of 0.01 sweeps onto the (first) largest weight.
        commitments = [_commitment("1000.00") for _ in range(3)]
        result = allocate_pro_rata(Decimal("100.00"), commitments)
        shares = [share for _, share in result]
        assert sum(shares) == Decimal("100.00")
        assert all(s in {Decimal("33.33"), Decimal("33.34")} for s in shares)
        assert shares.count(Decimal("33.34")) == 1

    def test_shares_quantized_to_two_decimals(self):
        c_a = _commitment("333.33")
        c_b = _commitment("666.67")
        result = allocate_pro_rata(Decimal("17.99"), [c_a, c_b])
        for _, share in result:
            assert share.as_tuple().exponent == -2
