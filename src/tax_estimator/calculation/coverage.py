"""Executable coverage contract for source-checked calculation profiles.

This registry is deliberately independent of rule-file discovery: a file on disk
does not make a jurisdiction available to callers.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from pathlib import Path


class CoverageStatus(StrEnum):
    ENABLED = "enabled"
    PENDING = "pending"
    BLOCKED = "blocked"


class UnsupportedCoverageError(ValueError):
    """A requested jurisdiction, period or profile has no verified policy."""


@dataclass(frozen=True)
class CoverageEntry:
    jurisdiction_id: str
    tax_year: int
    profile_id: str
    status: CoverageStatus
    native_period_id: str
    period_label: str
    period_start: date
    period_end: date
    earnings_start: date
    earnings_end: date
    parent_id: str | None
    dependencies: tuple[str, ...]
    rule_paths: tuple[str, ...]
    policy_id: str
    rules_version: str
    currency: str
    rounding: str
    income_categories: frozenset[str]
    loss_treatment: str
    locality_status: str
    payroll_scope: str
    evidence_ids: tuple[str, ...]
    verified_on: date | None
    unavailable_reason: str | None = None

    def __post_init__(self) -> None:
        if self.period_end < self.period_start or self.earnings_end < self.earnings_start:
            raise ValueError("Coverage periods must have inclusive start/end dates")
        if self.status == CoverageStatus.ENABLED:
            if not self.rule_paths or not self.evidence_ids or self.verified_on is None:
                raise ValueError("Enabled coverage requires rules, evidence and verification")
            if self.unavailable_reason:
                raise ValueError("Enabled coverage cannot have an unavailable reason")
        elif not self.unavailable_reason:
            raise ValueError("Unavailable coverage requires a public-safe reason")


US_VANILLA_PROFILE = "us_single_40_resident_employee_standard_direct_securities_v1"
US_VANILLA_INCOME = frozenset({
    "employment_wages", "dividends_ordinary", "dividends_qualified",
    "capital_gains_short_term", "capital_gains_long_term",
})

_RULES_ROOT = Path(__file__).resolve().parents[3] / "rules"

SOURCE_LEDGER: dict[str, str] = {
    "IRS-REV-PROC-2025-32": "https://www.irs.gov/irb/2025-45_IRB",
    "SSA-2026-WAGE-BASE": "https://www.ssa.gov/oact/COLA/cbb.html",
    "TX-CONST-ART-8-24A": "https://tcss.legis.texas.gov/resources/CN/htm/CN.8.htm",
    "AK-NO-PERSONAL-IT": "https://labor.alaska.gov/lss/forms/Pam400.pdf",
    "FL-NO-PERSONAL-IT": "https://floridarevenue.com/faq/Pages/FAQDetails.aspx?FAQID=1466",
    "NV-NO-PERSONAL-IT": "https://tax.nv.gov/about-nevada-department-of-taxation/income-tax-in-nevada/",
    "NH-INTEREST-DIVIDEND-REPEAL": "https://www.revenue.nh.gov/news-and-media/repeal-nh-interest-and-dividends-tax-now-effect",
    "SD-NO-PERSONAL-IT": "https://dor.sd.gov/individuals/taxes/",
    "TN-HALL-TAX-REPEAL": "https://www.tn.gov/revenue/taxes/hall-income-tax.html",
    "WY-NO-PERSONAL-IT": "https://wyomingbusiness.org/why-wyoming/business-resources/",
}

_COVERAGE: dict[tuple[str, int, str], CoverageEntry] = {
    ("US-TX", 2026, US_VANILLA_PROFILE): CoverageEntry(
        jurisdiction_id="US-TX",
        tax_year=2026,
        profile_id=US_VANILLA_PROFILE,
        status=CoverageStatus.ENABLED,
        native_period_id="US-TY2026",
        period_label="US tax year 2026",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
        earnings_start=date(2026, 1, 1),
        earnings_end=date(2026, 12, 31),
        parent_id="US",
        dependencies=("US", "US-TX"),
        rule_paths=("federal/2026.yaml", "states/2026/tx.yaml"),
        policy_id="us_federal_2026_plus_no_individual_income_tax_v1",
        rules_version="2026.1.0",
        currency="USD",
        rounding="federal Form 1040 whole dollars; state zero",
        income_categories=US_VANILLA_INCOME,
        loss_treatment="federal Schedule D; no Texas individual tax",
        locality_status="none",
        payroll_scope="federal employee FICA only",
        evidence_ids=(
            "IRS-REV-PROC-2025-32", "SSA-2026-WAGE-BASE", "TX-CONST-ART-8-24A",
        ),
        verified_on=date(2026, 9, 30),
    ),
}


_ZERO_TAX_STATE_EVIDENCE = {
    "AK": "AK-NO-PERSONAL-IT",
    "FL": "FL-NO-PERSONAL-IT",
    "NV": "NV-NO-PERSONAL-IT",
    "NH": "NH-INTEREST-DIVIDEND-REPEAL",
    "SD": "SD-NO-PERSONAL-IT",
    "TN": "TN-HALL-TAX-REPEAL",
    "WY": "WY-NO-PERSONAL-IT",
}

for _state_code, _state_evidence in _ZERO_TAX_STATE_EVIDENCE.items():
    _entry = CoverageEntry(
        jurisdiction_id=f"US-{_state_code}",
        tax_year=2026,
        profile_id=US_VANILLA_PROFILE,
        status=CoverageStatus.ENABLED,
        native_period_id="US-TY2026",
        period_label="US tax year 2026",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 12, 31),
        earnings_start=date(2026, 1, 1),
        earnings_end=date(2026, 12, 31),
        parent_id="US",
        dependencies=("US", f"US-{_state_code}"),
        rule_paths=("federal/2026.yaml", f"states/2026/{_state_code.lower()}.yaml"),
        policy_id="us_federal_2026_plus_no_individual_income_tax_v1",
        rules_version="2026.1.0",
        currency="USD",
        rounding="federal Form 1040 whole dollars; state zero",
        income_categories=US_VANILLA_INCOME,
        loss_treatment="federal Schedule D; no individual state income tax",
        locality_status="none",
        payroll_scope="federal employee FICA only",
        evidence_ids=("IRS-REV-PROC-2025-32", "SSA-2026-WAGE-BASE", _state_evidence),
        verified_on=date(2026, 10, 1),
    )
    _COVERAGE[(_entry.jurisdiction_id, _entry.tax_year, _entry.profile_id)] = _entry


def coverage_entry(
    jurisdiction_id: str, tax_year: int, profile_id: str = US_VANILLA_PROFILE
) -> CoverageEntry | None:
    """Return registered coverage, including pending entries for public discovery."""
    return _COVERAGE.get((jurisdiction_id.upper(), tax_year, profile_id))


def enabled_coverage(tax_year: int, profile_id: str = US_VANILLA_PROFILE) -> tuple[CoverageEntry, ...]:
    """Return enabled entries; never infer availability from files on disk."""
    return tuple(
        entry for entry in _COVERAGE.values()
        if entry.tax_year == tax_year
        and entry.profile_id == profile_id
        and entry.status == CoverageStatus.ENABLED
    )


def require_coverage(
    jurisdiction_id: str,
    tax_year: int,
    profile_id: str = US_VANILLA_PROFILE,
    *,
    rules_root: Path | None = None,
    income_categories: frozenset[str] | None = None,
) -> CoverageEntry:
    """Enforce registry, income capabilities and all required rule dependencies."""
    entry = coverage_entry(jurisdiction_id, tax_year, profile_id)
    if entry is None:
        raise UnsupportedCoverageError(
            f"{jurisdiction_id} has no supported {tax_year} {profile_id} coverage"
        )
    if entry.status != CoverageStatus.ENABLED:
        raise UnsupportedCoverageError(entry.unavailable_reason or "Coverage is unavailable")
    if income_categories and not income_categories <= entry.income_categories:
        unsupported = ", ".join(sorted(income_categories - entry.income_categories))
        raise UnsupportedCoverageError(f"Unsupported income categories: {unsupported}")
    root = rules_root or _RULES_ROOT
    missing = [path for path in entry.rule_paths if not (root / path).is_file()]
    if missing:
        raise UnsupportedCoverageError(
            f"{jurisdiction_id} {tax_year} coverage is unavailable: required rules are missing"
        )
    return entry


def require_aligned_earnings_period(entries: tuple[CoverageEntry, ...]) -> None:
    """Prevent a ranking between different income-earning windows."""
    periods = {(entry.earnings_start, entry.earnings_end) for entry in entries}
    if len(periods) > 1:
        raise UnsupportedCoverageError(
            "2026 comparison cannot rank different earnings periods"
        )


def enabled_us_states(tax_year: int, *, rules_root: Path | None = None) -> frozenset[str]:
    """State codes enabled for the US vanilla profile in a given year."""
    states = set()
    for entry in enabled_coverage(tax_year):
        if entry.parent_id != "US" or entry.jurisdiction_id.count("-") != 1:
            continue
        try:
            require_coverage(
                entry.jurisdiction_id, tax_year, rules_root=rules_root
            )
        except UnsupportedCoverageError:
            continue
        states.add(entry.jurisdiction_id.removeprefix("US-"))
    return frozenset(states)
