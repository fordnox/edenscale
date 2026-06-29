"""Allocation helpers for capital calls and distributions.

A pro-rata split divides ``total_amount`` across commitments in proportion
to their ``committed_amount``. Each share is quantized to two decimal
places (matching ``Numeric(18, 2)`` columns) and the rounding remainder is
applied to the largest commitment so the per-share sum reconciles exactly
with the input total.
"""

from decimal import ROUND_HALF_UP, Decimal

from app.models.commitment import Commitment

_QUANTUM = Decimal("0.01")


def allocate_pro_rata(
    total_amount: Decimal,
    commitments: list[Commitment],
) -> list[tuple[Commitment, Decimal]]:
    if not commitments:
        return []
    total = Decimal(total_amount)
    if total < Decimal("0"):
        raise ValueError("total_amount must be greater than or equal to 0")

    weights = [Decimal(c.committed_amount) for c in commitments]  # type: ignore[invalid-argument-type]
    if total == Decimal("0"):
        return [(c, Decimal("0.00")) for c in commitments]

    total_committed = sum(weights, Decimal("0"))
    if total_committed <= Decimal("0"):
        raise ValueError(
            "Cannot allocate pro-rata: total committed amount must be greater than 0"
        )

    shares: list[Decimal] = [
        (total * weight / total_committed).quantize(_QUANTUM, rounding=ROUND_HALF_UP)
        for weight in weights
    ]
    remainder = total.quantize(_QUANTUM, rounding=ROUND_HALF_UP) - sum(
        shares, Decimal("0")
    )
    if remainder != Decimal("0"):
        largest_index = max(range(len(commitments)), key=lambda i: weights[i])
        shares[largest_index] += remainder
    return list(zip(commitments, shares))
