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
    CAPITAL_GAINS_EXCISE = "capital_gains_excise"


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
    treatment: str = "deduction"


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
            b for b in self.brackets if b.filing_status == filing_status or b.filing_status == "all"
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

    # Character and federal-return inputs used by reviewed 2025 state policies.
    # None means unavailable; zero means a known zero. Ordinary dividends already
    # include the qualified-dividend subset.
    qualified_dividends: Decimal | None = None
    net_short_term_gains: Decimal | None = None
    net_long_term_gains: Decimal | None = None
    federal_agi_capital_gain: Decimal | None = None
    federal_income_tax_after_nonrefundable_credits: Decimal | None = None
    federal_refundable_credits: Decimal | None = None
    federal_earned_income_credit: Decimal | None = None
    federal_niit: Decimal | None = None
    federal_additional_medicare_tax: Decimal | None = None
    federal_self_employment_tax: Decimal | None = None
    employee_social_security_tax: Decimal | None = None
    employee_medicare_tax: Decimal | None = None
    federal_deduction_amount: Decimal | None = None
    # Federal IRC section 199A deduction already subtracted in federal_taxable_income
    # (Form 1040 line 13a). Zero for wage/investment-only returns. States that do
    # not allow it add it back; see policy_common.QBI_CONFORMITY_2025.
    federal_qbi_deduction: Decimal = Decimal(0)

    # Deductions
    use_standard_deduction: bool = True
    itemized_deductions: Decimal = Decimal(0)

    # Personal info
    is_resident: bool = True
    num_dependents: int = 0
    age_65_or_older: bool = False
    is_blind: bool = False
    can_be_claimed_as_dependent: bool = False
    spouse_age_65_or_older: bool = False
    spouse_is_blind: bool = False
    taxpayer_age_at_year_end: int | None = None
    spouse_age_at_year_end: int | None = None
    federal_eitc_eligibility_asserted: bool | None = None

    # Specialized policies are restricted to the reviewed baseline. Direct
    # compatibility calls default to the generic, explicitly unvalidated path.
    baseline_profile_supported: bool = False
    unsupported_profile_reasons: tuple[str, ...] = ()

    # Typed scenario fact for Arizona's post-2011 capital-gain subtraction.
    az_post_2011_eligible_long_term_gains: Decimal | None = None

    # For credit calculations
    taxes_paid_to_other_states: Decimal = Decimal(0)

    @property
    def federal_taxable_income_before_qbi(self) -> Decimal:
        """Federal taxable income before the section 199A deduction."""
        return self.federal_taxable_income + self.federal_qbi_deduction


@dataclass
class StateBracketBreakdown:
    """Breakdown of tax by bracket."""

    bracket_id: str
    bracket_min: Decimal
    bracket_max: Decimal | None
    rate: Decimal
    income_in_bracket: Decimal
    tax_in_bracket: Decimal


@dataclass(frozen=True)
class StateAmountComponent:
    """Named addition or subtraction used to reconcile a state base."""

    component_id: str
    name: str
    amount: Decimal


@dataclass(frozen=True)
class StateCreditComponent:
    """A state credit with its legally available and applied amounts."""

    credit_id: str
    name: str
    amount_available: Decimal
    amount_applied: Decimal
    is_refundable: bool


@dataclass(frozen=True)
class RateScheduleResult:
    """Result of a state rate schedule, including published-base rounding."""

    tax: Decimal
    bracket_breakdown: tuple[StateBracketBreakdown, ...]
    marginal_rate: Decimal
    published_base_adjustment: Decimal = Decimal(0)


@dataclass
class StatePolicyComputation:
    """Auditable intermediate output from a reviewed 2025 state policy."""

    starting_income: Decimal
    state_agi: Decimal
    taxable_income: Decimal
    tax_type_override: StateTaxType | None = None
    additions: tuple[StateAmountComponent, ...] = ()
    subtractions: tuple[StateAmountComponent, ...] = ()
    deduction_type: str = "none"
    deduction_amount: Decimal = Decimal(0)
    personal_exemption: Decimal = Decimal(0)
    dependent_exemption: Decimal = Decimal(0)
    ordinary_taxable_income: Decimal = Decimal(0)
    preferential_taxable_income: Decimal = Decimal(0)
    ordinary_tax: Decimal = Decimal(0)
    preferential_tax: Decimal = Decimal(0)
    other_base_tax: Decimal = Decimal(0)
    tax_before_credits: Decimal = Decimal(0)
    surtax: Decimal = Decimal(0)
    recapture: Decimal = Decimal(0)
    credits: tuple[StateCreditComponent, ...] = ()
    marginal_rate: Decimal = Decimal(0)
    bracket_breakdown: tuple[StateBracketBreakdown, ...] = ()
    assumptions: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


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
    starting_point: str = "federal_agi"
    additions: list[StateAmountComponent] = field(default_factory=list)
    subtractions: list[StateAmountComponent] = field(default_factory=list)

    # Exemptions
    personal_exemption: Decimal = Decimal(0)
    dependent_exemption: Decimal = Decimal(0)

    # Taxable income
    taxable_income: Decimal = Decimal(0)
    ordinary_taxable_income: Decimal = Decimal(0)
    preferential_taxable_income: Decimal = Decimal(0)

    # Tax calculation
    tax_before_credits: Decimal = Decimal(0)
    ordinary_tax: Decimal = Decimal(0)
    preferential_tax: Decimal = Decimal(0)
    other_base_tax: Decimal = Decimal(0)
    surtax: Decimal = Decimal(0)
    recapture: Decimal = Decimal(0)
    total_tax: Decimal = Decimal(0)

    # Credits
    credits: Decimal = Decimal(0)
    nonrefundable_credits: Decimal = Decimal(0)
    refundable_credits: Decimal = Decimal(0)
    credit_components: list[StateCreditComponent] = field(default_factory=list)
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
    assumptions: list[str] = field(default_factory=list)

    @property
    def no_tax_message(self) -> str | None:
        """Get message if state has no income tax."""
        if not self.has_income_tax and self.total_tax == 0:
            return f"{self.state_name} has no state income tax"
        return None
