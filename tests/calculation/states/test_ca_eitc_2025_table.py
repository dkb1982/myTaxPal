from tax_estimator.calculation.states.ca_eitc_2025 import (
    CA_EITC_NO_CHILD_TABLE_2025,
    SOURCE_SHA256,
    SOURCE_URL,
)


def _credit_for_whole_dollar(amount: int) -> int:
    return next(
        credit
        for lower, upper, credit in CA_EITC_NO_CHILD_TABLE_2025
        if lower <= amount <= upper
    )


def test_no_child_table_is_complete_contiguous_official_2025_table() -> None:
    rows = CA_EITC_NO_CHILD_TABLE_2025

    assert SOURCE_URL == "https://www.ftb.ca.gov/forms/2025/2025-3514-booklet.html"
    assert SOURCE_SHA256 == "67aea592cacf3f1d6bf4766a2bf4bfe9fb38b72939e9b146df495a5dfc7e9e22"
    assert len(rows) == 658
    assert rows[0][:2] == (1, 50)
    assert rows[-1] == (32851, 32900, 1)
    assert all(upper - lower == 49 for lower, upper, _credit in rows)
    assert all(
        upper + 1 == next_lower
        for (_lower, upper, _credit), (next_lower, _next_upper, _next_credit)
        in zip(rows, rows[1:])
    )


def test_no_child_table_matches_official_reference_bands() -> None:
    assert _credit_for_whole_dollar(10_000) == 211
    assert _credit_for_whole_dollar(25_000) == 73
    assert _credit_for_whole_dollar(32_851) == 1
    assert _credit_for_whole_dollar(32_900) == 1
