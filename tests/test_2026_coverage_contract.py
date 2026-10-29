"""Coverage is a gate, not a synonym for a discovered YAML file."""

from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from tax_estimator.calculation import coverage
from tax_estimator.calculation.coverage import (
    SOURCE_LEDGER,
    CoverageStatus,
    UnsupportedCoverageError,
    coverage_entry,
    enabled_us_states,
    require_aligned_earnings_period,
    require_coverage,
)


def test_texas_2026_contract_is_complete_and_executable() -> None:
    entry = require_coverage("US-TX", 2026)

    assert entry.status == CoverageStatus.ENABLED
    assert entry.native_period_id == "US-TY2026"
    assert entry.period_start == entry.earnings_start == date(2026, 1, 1)
    assert entry.period_end == entry.earnings_end == date(2026, 12, 31)
    assert entry.dependencies == ("US", "US-TX")
    assert entry.locality_status == "none"
    assert entry.currency == "USD"
    assert set(entry.evidence_ids) <= set(SOURCE_LEDGER)
    assert "TX" in enabled_us_states(2026)


def test_unregistered_or_missing_rule_coverage_is_rejected(monkeypatch) -> None:
    # Newark has 2025 rules but is not registered for 2026.
    assert coverage_entry("US-NJ-NEW", 2026) is None
    with pytest.raises(UnsupportedCoverageError, match="no supported"):
        require_coverage("US-NJ-NEW", 2026)
    # A pending state is discoverable but never computable. No state is pending
    # now, so mark Colorado pending for this check.
    key = ("US-CO", 2026, coverage.US_VANILLA_PROFILE)
    monkeypatch.setitem(coverage._COVERAGE, key, replace(
        coverage._COVERAGE[key], status=CoverageStatus.PENDING,
        unavailable_reason="Colorado 2026 figures are not yet published.",
    ))
    pending = coverage_entry("US-CO", 2026)
    assert pending is not None and pending.unavailable_reason
    with pytest.raises(UnsupportedCoverageError, match="Colorado"):
        require_coverage("US-CO", 2026)
    with pytest.raises(UnsupportedCoverageError, match="required rules are missing"):
        require_coverage(
            "US-TX", 2026,
            rules_root=Path(__file__).parent / "nonexistent_rules_root",
        )


def test_unsupported_income_category_and_mismatched_period_block_ranking() -> None:
    texas = require_coverage("US-TX", 2026)
    with pytest.raises(UnsupportedCoverageError, match="Unsupported income categories"):
        require_coverage("US-TX", 2026, income_categories=frozenset({"rental"}))

    different_window = replace(
        texas,
        jurisdiction_id="SG",
        earnings_start=date(2025, 1, 1),
        earnings_end=date(2025, 12, 31),
    )
    with pytest.raises(UnsupportedCoverageError, match="different earnings periods"):
        require_aligned_earnings_period((texas, different_window))
    require_aligned_earnings_period((texas, texas))
