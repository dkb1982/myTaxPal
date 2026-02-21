"""
Pydantic models for tax calculation results.

These models define the structure of calculation outputs.
All monetary values use Decimal for precision.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, computed_field


class BracketBreakdown(BaseModel):
    """Breakdown of tax calculated in a single bracket."""

    bracket_id: str = Field(..., description="Unique bracket identifier")
    bracket_min: Decimal = Field(..., description="Lower bound of bracket")
    bracket_max: Decimal | None = Field(None, description="Upper bound (None = unlimited)")
    rate: Decimal = Field(..., description="Tax rate as decimal")
    income_in_bracket: Decimal = Field(..., description="Income taxed in this bracket")
    tax_in_bracket: Decimal = Field(..., description="Tax computed for this bracket")


class PreferentialRateBreakdown(BaseModel):
    """Breakdown of tax at a preferential rate (0%/15%/20%)."""

    rate: Decimal = Field(..., description="Tax rate (0.00, 0.15, or 0.20)")
    income_in_bracket: Decimal = Field(..., description="Income taxed at this rate")
    tax_in_bracket: Decimal = Field(..., description="Tax at this rate")


class DeductionResult(BaseModel):
    """Result of deduction calculation."""

    method: str = Field(..., description="'standard' or 'itemized'")
    standard_deduction_available: Decimal = Field(
        ..., description="Standard deduction amount available"
    )
    itemized_deduction_total: Decimal = Field(
        default=Decimal(0), description="Total itemized deductions"
    )
    deduction_used: Decimal = Field(..., description="Deduction amount applied")
    additional_deduction: Decimal = Field(
        default=Decimal(0), description="Additional deduction for age/blindness"
    )


class CreditDetail(BaseModel):
    """Details of a single tax credit."""

    credit_id: str = Field(..., description="Unique credit identifier")
    credit_name: str = Field(..., description="Display name of the credit")
    credit_amount: Decimal = Field(..., description="Full credit amount calculated")
    amount_used: Decimal = Field(..., description="Amount actually applied")
    is_refundable: bool = Field(..., description="Whether credit is refundable")


class CreditsResult(BaseModel):
    """Result of credits calculation."""

    nonrefundable_credits: list[CreditDetail] = Field(default_factory=list)
    refundable_credits: list[CreditDetail] = Field(default_factory=list)
    total_nonrefundable: Decimal = Field(default=Decimal(0))
    total_refundable: Decimal = Field(default=Decimal(0))
    total_credits: Decimal = Field(default=Decimal(0))


class FederalTaxResult(BaseModel):
    """Complete federal tax calculation result."""

    # Income
    gross_income: Decimal = Field(..., description="Total gross income")
    total_adjustments: Decimal = Field(
        default=Decimal(0), description="Above-the-line adjustments"
    )
    adjusted_gross_income: Decimal = Field(..., description="AGI")

    # Deductions
    deduction: DeductionResult = Field(..., description="Deduction details")

    # Taxable income
    taxable_income: Decimal = Field(..., description="AGI minus deductions")
    ordinary_income: Decimal = Field(default=Decimal(0), description="Ordinary portion of taxable income")
    preferential_income: Decimal = Field(default=Decimal(0), description="LTCG + qualified dividends portion")

    # Tax computation
    tax_before_credits: Decimal = Field(..., description="Tax from brackets")
    ordinary_tax: Decimal = Field(default=Decimal(0), description="Tax on ordinary income")
    preferential_tax: Decimal = Field(default=Decimal(0), description="Tax on preferential income")
    preferential_rate_breakdown: list[PreferentialRateBreakdown] = Field(
        default_factory=list, description="Breakdown of 0%/15%/20% preferential rates"
    )
    bracket_breakdown: list[BracketBreakdown] = Field(
        default_factory=list, description="Tax by bracket"
    )

    # Credits
    credits: CreditsResult = Field(default_factory=CreditsResult)

    # Other taxes
    self_employment_tax: Decimal = Field(default=Decimal(0))
    additional_medicare_tax: Decimal = Field(default=Decimal(0))
    net_investment_income_tax: Decimal = Field(default=Decimal(0))

    # Final amounts
    total_tax: Decimal = Field(..., description="Total tax liability")
    total_withholding: Decimal = Field(default=Decimal(0), description="Total withheld")
    total_payments: Decimal = Field(default=Decimal(0), description="Estimated payments")

    @computed_field
    @property
    def refund_or_owed(self) -> Decimal:
        """Amount owed (positive) or refund (negative)."""
        return self.total_tax - self.total_withholding - self.total_payments

    effective_rate: Decimal = Field(default=Decimal(0), description="Effective tax rate")
    marginal_rate: Decimal = Field(default=Decimal(0), description="Marginal tax rate")


class StateTaxResult(BaseModel):
    """State tax calculation result."""

    jurisdiction_id: str = Field(..., description="State jurisdiction ID (e.g., US-CA)")
    jurisdiction_name: str = Field(..., description="State name")

    # Tax characteristics
    has_income_tax: bool = Field(default=True, description="Whether state has income tax")
    tax_type: str = Field(default="graduated", description="Type of tax: none, flat, graduated")
    filing_status: str = Field(default="single", description="Filing status used")

    # Income (may differ from federal for some states)
    gross_income: Decimal = Field(default=Decimal(0), description="Gross income")
    state_agi: Decimal = Field(default=Decimal(0), description="State AGI")
    state_taxable_income: Decimal = Field(...)
    starting_point: str = Field(
        default="federal_agi", description="What state uses as starting point"
    )

    # Deductions
    deduction_type: str = Field(default="standard", description="standard, itemized, or none")
    deduction_amount: Decimal = Field(default=Decimal(0), description="Deduction applied")
    personal_exemption: Decimal = Field(default=Decimal(0), description="Personal exemption")
    dependent_exemption: Decimal = Field(default=Decimal(0), description="Dependent exemption")

    # Tax
    tax_before_credits: Decimal = Field(...)
    surtax: Decimal = Field(default=Decimal(0), description="Any surtaxes (e.g., MA millionaire)")
    bracket_breakdown: list[BracketBreakdown] = Field(default_factory=list)
    state_credits: Decimal = Field(default=Decimal(0))
    total_state_tax: Decimal = Field(...)

    # Rates
    effective_rate: Decimal = Field(default=Decimal(0), description="Effective state tax rate")
    marginal_rate: Decimal = Field(default=Decimal(0), description="Marginal state tax rate")

    # Withholding
    state_withholding: Decimal = Field(default=Decimal(0))

    # Residency
    is_resident: bool = Field(default=True, description="Whether taxpayer is state resident")

    # Notes
    notes: list[str] = Field(default_factory=list, description="State-specific notes")

    @computed_field
    @property
    def state_refund_or_owed(self) -> Decimal:
        """State amount owed (positive) or refund (negative)."""
        return self.total_state_tax - self.state_withholding


class LocalTaxResult(BaseModel):
    """Local (city/county) tax calculation result."""

    jurisdiction_id: str = Field(..., description="Local jurisdiction ID (e.g., US-NY-NYC)")
    jurisdiction_name: str = Field(..., description="Local jurisdiction name")
    parent_state: str = Field(..., description="Parent state code")

    # Tax characteristics
    has_income_tax: bool = Field(default=True, description="Whether jurisdiction has income tax")
    tax_type: str = Field(
        default="city_income_tax",
        description="Type: city_income_tax, wage_tax, earnings_tax, etc."
    )

    # Income
    taxable_income: Decimal = Field(..., description="Income subject to local tax")

    # Tax
    rate_applied: Decimal = Field(..., description="Rate applied")
    tax_before_credits: Decimal = Field(default=Decimal(0))
    credit_for_taxes_paid_elsewhere: Decimal = Field(default=Decimal(0))
    total_tax: Decimal = Field(..., description="Total local tax")
    net_tax: Decimal = Field(..., description="Net local tax after credits")

    # Rates
    effective_rate: Decimal = Field(default=Decimal(0))

    # Residency
    is_resident: bool = Field(default=True)

    # Notes
    notes: list[str] = Field(default_factory=list)


class FullUSResult(BaseModel):
    """
    Complete US tax calculation result.

    Combines federal, state, and local tax results with a summary.
    """

    federal: FederalTaxResult = Field(..., description="Federal tax result")
    state: StateTaxResult | None = Field(None, description="State tax result")
    locals: list[LocalTaxResult] = Field(default_factory=list, description="Local tax results")

    @computed_field
    @property
    def total_tax(self) -> Decimal:
        """Total tax across all jurisdictions."""
        total = self.federal.total_tax
        if self.state:
            total += self.state.total_state_tax
        for local in self.locals:
            total += local.total_tax
        return total

    @computed_field
    @property
    def total_effective_rate(self) -> Decimal:
        """Combined effective tax rate across all jurisdictions."""
        if self.federal.adjusted_gross_income <= 0:
            return Decimal(0)
        return (self.total_tax / self.federal.adjusted_gross_income).quantize(Decimal("0.0001"))

    @computed_field
    @property
    def breakdown_by_level(self) -> dict[str, Decimal]:
        """Tax breakdown by jurisdiction level."""
        return {
            "federal": self.federal.total_tax,
            "state": self.state.total_state_tax if self.state else Decimal(0),
            "local": sum(local.total_tax for local in self.locals),
        }


class CalculationResult(BaseModel):
    """
    Complete tax calculation result.

    Contains federal, state, and local tax results along with
    the calculation trace for auditing.
    """

    success: bool = Field(..., description="Whether calculation completed successfully")
    tax_year: int = Field(..., description="Tax year calculated")

    # Tax results by jurisdiction
    federal: FederalTaxResult | None = Field(None, description="Federal tax result")
    states: list[StateTaxResult] = Field(default_factory=list, description="State results")

    # Totals
    total_tax_liability: Decimal = Field(default=Decimal(0))
    total_withholding: Decimal = Field(default=Decimal(0))
    total_payments: Decimal = Field(default=Decimal(0))

    @computed_field
    @property
    def net_refund_or_owed(self) -> Decimal:
        """Net amount owed (positive) or refund (negative) across all jurisdictions."""
        return self.total_tax_liability - self.total_withholding - self.total_payments

    # Calculation metadata
    trace: dict[str, Any] | None = Field(
        None, description="Calculation trace for debugging"
    )
    warnings: list[str] = Field(default_factory=list, description="Calculation warnings")
    errors: list[str] = Field(default_factory=list, description="Calculation errors")

    # Disclaimers
    disclaimers: list[str] = Field(
        default_factory=lambda: [
            "This is an estimate only and should not be considered tax advice.",
            "Consult a qualified tax professional for your specific situation.",
            "Tax laws change frequently; verify all calculations with official sources.",
        ]
    )
