"""
Models for state tax calculations.

These models define the inputs and outputs for state tax calculations.
All monetary values use Decimal for precision.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any


class StateTaxType(str, Enum):
    """Type of state income tax."""

    NONE = "none"
    FLAT = "flat"
    GRADUATED = "graduated"
    INTEREST_DIVIDENDS_ONLY = "interest_dividends_only"


class StateStartingPoint(str, Enum):
    """Starting point for state taxable income calculation."""

    FEDERAL_AGI = "federal_agi"
    FEDERAL_TAXABLE_INCOME = "federal_taxable_income"
    STATE_DEFINED = "state_defined"
    NOT_APPLICABLE = "not_applicable"


@dataclass
class StateBracket:
    """A state tax bracket."""

    bracket_id: str
    filing_status: str
    income_from: Decimal
    income_to: Decimal | None
    rate: Decimal
    base_tax: Decimal


@dataclass
class StateSurtax:
    """A state surtax (e.g., MA millionaire tax)."""

    surtax_id: str
    name: str
    threshold: Decimal
    rate: Decimal
    filing_status: str
    description: str


@dataclass
class StateDeduction:
    """State deduction information."""

    standard_available: bool
    amounts: dict[str, Decimal]  # filing_status -> amount
    additional_amounts: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class StateExemption:
    """State exemption information."""

    personal_available: bool
    personal_amount: Decimal
    dependent_available: bool
    dependent_amount: Decimal


@dataclass
class StateRules:
    """
    Complete state tax rules.

    This model holds all tax rules for a single state.
    All values are PLACEHOLDERS and must be verified before production use.
    """

    state_code: str
    state_name: str
    tax_year: int
    has_income_tax: bool
    tax_type: StateTaxType
    starting_point: StateStartingPoint

    # Rates
    flat_rate: Decimal | None = None
    brackets: list[StateBracket] = field(default_factory=list)
    surtaxes: list[StateSurtax] = field(default_factory=list)

    # Deductions and exemptions
    deduction: StateDeduction | None = None
    exemption: StateExemption | None = None

    # Reciprocity
    reciprocity_states: list[str] = field(default_factory=list)

    # Local tax info
    has_local_income_tax: bool = False
    local_tax_mandatory: bool = False

    # Special notes
    special_notes: list[str] = field(default_factory=list)

    def get_brackets_for_status(self, filing_status: str) -> list[StateBracket]:
        """Get brackets for a specific filing status."""
        return [
            b for b in self.brackets
            if b.filing_status == filing_status or b.filing_status == "all"
        ]

    def get_standard_deduction(self, filing_status: str) -> Decimal:
        """Get standard deduction for a filing status."""
        if not self.deduction or not self.deduction.standard_available:
            return Decimal(0)
        return self.deduction.amounts.get(filing_status, Decimal(0))


@dataclass
class StateTaxInput:
    """Input for state tax calculation."""

    state_code: str
    tax_year: int
    filing_status: str

    # Income
    federal_agi: Decimal
    federal_taxable_income: Decimal

    # Income components (for special rules)
    wages: Decimal = Decimal(0)
    interest: Decimal = Decimal(0)
    dividends: Decimal = Decimal(0)
    capital_gains: Decimal = Decimal(0)
    retirement_income: Decimal = Decimal(0)

    # Deductions
    use_standard_deduction: bool = True
    itemized_deductions: Decimal = Decimal(0)

    # Personal info
    is_resident: bool = True
    num_dependents: int = 0
    age_65_or_older: bool = False
    is_blind: bool = False

    # For credit calculations
    taxes_paid_to_other_states: Decimal = Decimal(0)


@dataclass
class StateBracketBreakdown:
    """Breakdown of tax by bracket."""

    bracket_id: str
    bracket_min: Decimal
    bracket_max: Decimal | None
    rate: Decimal
    income_in_bracket: Decimal
    tax_in_bracket: Decimal


@dataclass
class StateTaxResult:
    """
    Result of a state tax calculation.

    Contains the calculated tax and supporting breakdown information.
    """

    # Identity
    state_code: str
    state_name: str
    tax_year: int
    filing_status: str

    # Tax characteristics
    has_income_tax: bool
    tax_type: StateTaxType

    # Income
    gross_income: Decimal
    starting_income: Decimal  # Federal AGI or taxable income
    state_agi: Decimal

    # Deductions
    deduction_type: str  # "standard", "itemized", "none"
    deduction_amount: Decimal

    # Exemptions
    personal_exemption: Decimal = Decimal(0)
    dependent_exemption: Decimal = Decimal(0)

    # Taxable income
    taxable_income: Decimal = Decimal(0)

    # Tax calculation
    tax_before_credits: Decimal = Decimal(0)
    surtax: Decimal = Decimal(0)
    total_tax: Decimal = Decimal(0)

    # Credits
    credits: Decimal = Decimal(0)
    credit_for_taxes_paid_elsewhere: Decimal = Decimal(0)

    # Final
    net_tax: Decimal = Decimal(0)
    effective_rate: Decimal = Decimal(0)
    marginal_rate: Decimal = Decimal(0)

    # Breakdown
    bracket_breakdown: list[StateBracketBreakdown] = field(default_factory=list)

    # Flags
    is_resident: bool = True

    # Warnings/notes
    warnings: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def no_tax_message(self) -> str | None:
        """Get message if state has no income tax."""
        if not self.has_income_tax:
            return f"{self.state_name} has no state income tax"
        return None
