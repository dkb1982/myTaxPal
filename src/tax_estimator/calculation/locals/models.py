"""
Models for local tax calculations.

These models define the inputs and outputs for local (city/county) tax calculations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any


class LocalTaxType(str, Enum):
    """Type of local income tax."""

    NONE = "none"
    CITY_INCOME_TAX = "city_income_tax"
    CITY_WAGE_TAX = "city_wage_tax"
    EARNINGS_TAX = "earnings_tax"
    OCCUPATIONAL_TAX = "occupational_tax"
    MUNICIPAL_INCOME_TAX = "municipal_income_tax"
    COUNTY_PIGGYBACK = "county_piggyback"
    PAYROLL_TAX = "payroll_tax"
    RESIDENT_SURCHARGE = "resident_surcharge"


class LocalTaxBase(str, Enum):
    """What income the local tax applies to."""

    ALL_INCOME = "all_income"
    EARNED_INCOME = "earned_income"  # Wages + SE income
    WAGES_ONLY = "wages_only"
    STATE_TAXABLE_INCOME = "state_taxable_income"
    STATE_TAX = "state_tax"  # For surcharges (% of state tax)


class ResidencyApplicability(str, Enum):
    """Who the local tax applies to."""

    RESIDENTS_ONLY = "residents_only"
    WORKERS_ONLY = "workers_only"
    BOTH_RESIDENTS_AND_WORKERS = "both_residents_and_workers"


@dataclass
class LocalBracket:
    """A local tax bracket."""

    bracket_id: str
    filing_status: str
    income_from: Decimal
    income_to: Decimal | None
    rate: Decimal
    base_tax: Decimal


@dataclass
class LocalFlatRates:
    """Flat rates for local tax (can differ by residency)."""

    rate: Decimal | None = None  # Single rate for all
    resident_rate: Decimal | None = None
    nonresident_rate: Decimal | None = None


@dataclass
class LocalCredit:
    """Credit for taxes paid to other jurisdictions."""

    allows_credit: bool
    max_credit_rate: Decimal | None = None
    credit_type: str = "taxes_paid_elsewhere"


@dataclass
class LocalRules:
    """
    Complete local tax rules.

    All values are PLACEHOLDERS and must be verified before production use.
    """

    jurisdiction_id: str
    jurisdiction_name: str
    parent_state: str
    tax_year: int

    has_income_tax: bool
    tax_type: LocalTaxType
    tax_base: LocalTaxBase
    applies_to: ResidencyApplicability

    # Rate info
    rate_type: str  # "flat" or "graduated"
    flat_rates: LocalFlatRates | None = None
    brackets: list[LocalBracket] = field(default_factory=list)

    # Surcharge info (for places like Yonkers)
    resident_surcharge_rate: Decimal | None = None
    surcharge_base: str | None = None  # e.g., "ny_state_tax"

    # Credits
    credit: LocalCredit | None = None

    # ZIP prefixes for this jurisdiction
    zip_prefixes: list[str] = field(default_factory=list)

    # Special notes
    special_notes: list[str] = field(default_factory=list)

    def get_rate_for_residency(self, is_resident: bool) -> Decimal:
        """Get the applicable rate based on residency."""
        if not self.flat_rates:
            return Decimal(0)

        if self.flat_rates.rate is not None:
            return self.flat_rates.rate

        if is_resident:
            return self.flat_rates.resident_rate or Decimal(0)
        else:
            return self.flat_rates.nonresident_rate or Decimal(0)

    def get_brackets_for_status(self, filing_status: str) -> list[LocalBracket]:
        """Get brackets for a specific filing status."""
        return [
            b for b in self.brackets
            if b.filing_status == filing_status or b.filing_status == "all"
        ]


@dataclass
class LocalTaxInput:
    """Input for local tax calculation."""

    jurisdiction_id: str
    tax_year: int
    filing_status: str

    # Residency
    is_resident: bool

    # Income
    total_income: Decimal
    wages: Decimal = Decimal(0)
    self_employment_income: Decimal = Decimal(0)
    state_taxable_income: Decimal = Decimal(0)
    state_tax: Decimal = Decimal(0)  # For surcharge calculations

    # Credits
    local_taxes_paid_elsewhere: Decimal = Decimal(0)


@dataclass
class LocalBracketBreakdown:
    """Breakdown of tax by bracket."""

    bracket_id: str
    bracket_min: Decimal
    bracket_max: Decimal | None
    rate: Decimal
    income_in_bracket: Decimal
    tax_in_bracket: Decimal


@dataclass
class LocalTaxResult:
    """
    Result of a local tax calculation.
    """

    # Identity
    jurisdiction_id: str
    jurisdiction_name: str
    parent_state: str
    tax_year: int
    filing_status: str

    # Tax characteristics
    has_income_tax: bool
    tax_type: LocalTaxType

    # Income used
    taxable_income: Decimal

    # Tax calculation
    rate_applied: Decimal
    tax_before_credits: Decimal = Decimal(0)
    total_tax: Decimal = Decimal(0)

    # Credits
    credit_for_taxes_paid_elsewhere: Decimal = Decimal(0)
    net_tax: Decimal = Decimal(0)

    # Rates
    effective_rate: Decimal = Decimal(0)
    marginal_rate: Decimal = Decimal(0)

    # Breakdown (for graduated)
    bracket_breakdown: list[LocalBracketBreakdown] = field(default_factory=list)

    # Residency
    is_resident: bool = True

    # Notes
    notes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
