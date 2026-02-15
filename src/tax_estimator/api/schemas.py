"""
API request and response schemas for the Tax Estimator.

These models define the structure of API requests and responses,
providing a clean separation between internal models and API contracts.

Based on the API specification in 09-api-specifications.md.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


# =============================================================================
# Enums
# =============================================================================


class FilingStatus(str, Enum):
    """Tax filing status options."""

    SINGLE = "single"
    MFJ = "mfj"  # Married Filing Jointly
    MFS = "mfs"  # Married Filing Separately
    HOH = "hoh"  # Head of Household
    QSS = "qss"  # Qualifying Surviving Spouse


class JurisdictionLevel(str, Enum):
    """Level of tax jurisdiction."""

    FEDERAL = "federal"
    STATE = "state"
    COUNTY = "county"
    CITY = "city"
    SCHOOL_DISTRICT = "school_district"


class EstimateStatus(str, Enum):
    """Status of an estimate calculation."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    ERROR = "error"


class WarningSeverity(str, Enum):
    """Severity level for warnings."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


# =============================================================================
# Request Models - Filer Information
# =============================================================================


def validate_date_string(value: str | None, field_name: str = "date") -> str | None:
    """
    Validate that a date string is a valid date, not just matching the pattern.

    Args:
        value: Date string in YYYY-MM-DD format, or None
        field_name: Name of the field for error messages

    Returns:
        The validated date string, or None

    Raises:
        ValueError: If the date is invalid (e.g., Feb 30)
    """
    if value is None:
        return None

    try:
        date.fromisoformat(value)
    except ValueError:
        raise ValueError(f"Invalid {field_name}: '{value}' is not a valid date")

    return value


class FilerInfo(BaseModel):
    """Filer information for tax estimate."""

    filing_status: FilingStatus = Field(..., description="Tax filing status")
    date_of_birth: str | None = Field(
        None,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="Date of birth (YYYY-MM-DD format)"
    )
    is_blind: bool = Field(default=False, description="Whether taxpayer is legally blind")
    can_be_claimed_as_dependent: bool = Field(
        default=False, description="Can be claimed as dependent on another return"
    )

    @field_validator("date_of_birth")
    @classmethod
    def validate_date_of_birth(cls, v: str | None) -> str | None:
        """Validate that date_of_birth is a valid date, not just matching pattern."""
        return validate_date_string(v, "date_of_birth")


class SpouseInfo(BaseModel):
    """Spouse information for MFJ/MFS."""

    date_of_birth: str | None = Field(
        None,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="Date of birth (YYYY-MM-DD format)"
    )
    is_blind: bool = Field(default=False, description="Whether spouse is legally blind")

    @field_validator("date_of_birth")
    @classmethod
    def validate_date_of_birth(cls, v: str | None) -> str | None:
        """Validate that date_of_birth is a valid date, not just matching pattern."""
        return validate_date_string(v, "date_of_birth")


class DependentInfo(BaseModel):
    """Information about a dependent."""

    first_name: str = Field(..., max_length=100, description="First name")
    last_name: str = Field(..., max_length=100, description="Last name")
    date_of_birth: str = Field(
        ...,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="Date of birth (YYYY-MM-DD format)"
    )
    relationship: str = Field(..., max_length=50, description="Relationship to taxpayer")
    ssn_last_four: str | None = Field(None, pattern=r"^\d{4}$", description="Last 4 of SSN")
    months_lived_with_taxpayer: int = Field(
        ..., ge=0, le=12, description="Months lived with taxpayer"
    )
    is_student: bool = Field(default=False, description="Full-time student")
    is_disabled: bool = Field(default=False, description="Permanently disabled")
    gross_income: Decimal | None = Field(None, ge=0, description="Dependent's gross income")

    @field_validator("date_of_birth")
    @classmethod
    def validate_date_of_birth(cls, v: str) -> str:
        """Validate that date_of_birth is a valid date, not just matching pattern."""
        result = validate_date_string(v, "date_of_birth")
        if result is None:
            raise ValueError("date_of_birth is required for dependents")
        return result


# =============================================================================
# Request Models - Residency
# =============================================================================


class AddressInfo(BaseModel):
    """Physical address for tax jurisdiction lookup."""

    street: str = Field(..., max_length=500, description="Street address")
    city: str = Field(..., max_length=100, description="City name")
    state: str = Field(..., pattern=r"^[A-Z]{2}$", description="Two-letter state code")
    zip: str = Field(..., pattern=r"^\d{5}(-\d{4})?$", description="ZIP code")


class ResidencyChange(BaseModel):
    """Record of residency change for part-year residents."""

    state: str = Field(..., pattern=r"^[A-Z]{2}$", description="State code")
    start_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="Start date (YYYY-MM-DD)")
    end_date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$", description="End date (YYYY-MM-DD)")
    type: Literal["resident", "nonresident"] = Field(..., description="Residency type")

    @field_validator("start_date")
    @classmethod
    def validate_start_date(cls, v: str) -> str:
        """Validate that start_date is a valid date."""
        result = validate_date_string(v, "start_date")
        if result is None:
            raise ValueError("start_date is required")
        return result

    @field_validator("end_date")
    @classmethod
    def validate_end_date(cls, v: str) -> str:
        """Validate that end_date is a valid date."""
        result = validate_date_string(v, "end_date")
        if result is None:
            raise ValueError("end_date is required")
        return result


class RemoteWorkInfo(BaseModel):
    """Remote work information for multi-state taxation."""

    is_remote: bool = Field(..., description="Whether taxpayer works remotely")
    remote_days_per_year: int | None = Field(None, ge=0, le=365, description="Remote days")
    office_days_per_year: int | None = Field(None, ge=0, le=365, description="Office days")
    employer_required: bool | None = Field(None, description="If remote work is employer required")


class ResidencyInfo(BaseModel):
    """Residency information for state tax calculation."""

    residence_state: str = Field(
        ..., min_length=2, max_length=2, description="Primary residence state code"
    )
    residence_city: str | None = Field(None, max_length=100, description="City of residence")
    residence_zip: str | None = Field(None, pattern=r"^\d{5}(-\d{4})?$", description="ZIP code")
    residence_county: str | None = Field(None, max_length=100, description="County name")
    residence_address: AddressInfo | None = Field(None, description="Full address")
    is_part_year: bool = Field(default=False, description="Part-year resident")
    residency_changes: list[ResidencyChange] | None = Field(None, description="Residency changes")
    work_state: str | None = Field(None, min_length=2, max_length=2, description="State where work is performed")
    work_city: str | None = Field(None, max_length=100, description="City where work is performed")
    work_location_same_as_residence: bool = Field(
        default=True, description="Work location same as residence"
    )
    remote_work: RemoteWorkInfo | None = Field(None, description="Remote work details")


# =============================================================================
# Request Models - Income
# =============================================================================


class WageIncomeInfo(BaseModel):
    """W-2 wage income from an employer."""

    employer_name: str = Field(..., max_length=200, description="Employer name")
    employer_state: str = Field(..., min_length=2, max_length=2, description="Employer state")
    employer_city: str | None = Field(None, max_length=100, description="Employer city")
    gross_wages: Decimal = Field(..., ge=0, description="Gross wages (Box 1)")
    federal_withholding: Decimal = Field(default=Decimal(0), ge=0, description="Federal withheld")
    state_withholding: Decimal = Field(default=Decimal(0), ge=0, description="State withheld")
    local_withholding: Decimal = Field(default=Decimal(0), ge=0, description="Local withheld")
    social_security_wages: Decimal | None = Field(None, ge=0, description="SS wages (Box 3)")
    medicare_wages: Decimal | None = Field(None, ge=0, description="Medicare wages (Box 5)")
    state_wages: Decimal | None = Field(None, ge=0, description="State wages (Box 16)")
    local_wages: Decimal | None = Field(None, ge=0, description="Local wages (Box 18)")
    retirement_contributions: Decimal | None = Field(None, ge=0, description="401k etc.")


class InterestIncomeInfo(BaseModel):
    """Interest income."""

    taxable: Decimal = Field(default=Decimal(0), ge=0, description="Taxable interest")
    tax_exempt: Decimal = Field(default=Decimal(0), ge=0, description="Tax-exempt interest")
    tax_exempt_state: str | None = Field(None, description="State for municipal bonds")


class DividendIncomeInfo(BaseModel):
    """Dividend income."""

    ordinary: Decimal = Field(default=Decimal(0), ge=0, description="Ordinary dividends")
    qualified: Decimal = Field(default=Decimal(0), ge=0, description="Qualified dividends")

    @field_validator("qualified")
    @classmethod
    def qualified_not_exceeding_ordinary(cls, v: Decimal, info) -> Decimal:
        """Ensure qualified dividends don't exceed ordinary dividends."""
        ordinary = info.data.get("ordinary", Decimal(0))
        if v > ordinary:
            raise ValueError("Qualified dividends cannot exceed ordinary dividends")
        return v


class CapitalGainsInfo(BaseModel):
    """Capital gains and losses."""

    short_term_gain: Decimal = Field(default=Decimal(0), description="Short-term gains")
    short_term_loss: Decimal = Field(default=Decimal(0), ge=0, description="Short-term losses")
    long_term_gain: Decimal = Field(default=Decimal(0), description="Long-term gains")
    long_term_loss: Decimal = Field(default=Decimal(0), ge=0, description="Long-term losses")
    carryover_loss: Decimal = Field(default=Decimal(0), ge=0, description="Carryover from prior years")


class EquityCompensationInfo(BaseModel):
    """Equity compensation (RSUs, ISOs, NSOs)."""

    type: Literal["rsu", "iso", "nso"] = Field(..., description="Type of equity")
    grant_date: str | None = Field(None, description="Grant date")
    vest_date: str | None = Field(None, description="Vest date")
    exercise_date: str | None = Field(None, description="Exercise date (options)")
    shares: int = Field(..., ge=1, description="Number of shares")
    fmv_at_vest: Decimal | None = Field(None, ge=0, description="FMV at vest")
    fmv_at_exercise: Decimal | None = Field(None, ge=0, description="FMV at exercise")
    exercise_price: Decimal | None = Field(None, ge=0, description="Exercise price")
    income: Decimal = Field(..., ge=0, description="Taxable income amount")
    grant_state: str | None = Field(None, description="State at grant")
    vest_state: str | None = Field(None, description="State at vest")


class SelfEmploymentInfo(BaseModel):
    """Self-employment income."""

    business_name: str | None = Field(None, max_length=200, description="Business name")
    gross_income: Decimal = Field(..., ge=0, description="Gross business income")
    expenses: Decimal = Field(default=Decimal(0), ge=0, description="Business expenses")
    state: str | None = Field(None, min_length=2, max_length=2, description="State where business operates")


class RentalIncomeInfo(BaseModel):
    """Rental property income."""

    property_address: str | None = Field(None, max_length=500, description="Property address")
    property_state: str = Field(..., min_length=2, max_length=2, description="Property state")
    gross_rent: Decimal = Field(..., ge=0, description="Gross rental income")
    expenses: Decimal = Field(default=Decimal(0), ge=0, description="Rental expenses")
    depreciation: Decimal = Field(default=Decimal(0), ge=0, description="Depreciation")


class RetirementIncomeInfo(BaseModel):
    """Retirement income from various sources."""

    social_security: Decimal = Field(default=Decimal(0), ge=0, description="Social Security")
    pension: Decimal = Field(default=Decimal(0), ge=0, description="Pension income")
    ira_distribution: Decimal = Field(default=Decimal(0), ge=0, description="IRA distributions")
    roth_distribution: Decimal = Field(default=Decimal(0), ge=0, description="Roth distributions")


class OtherIncomeInfo(BaseModel):
    """Other income not covered by specific categories."""

    description: str = Field(..., max_length=500, description="Description of income")
    amount: Decimal = Field(..., description="Income amount")
    type: str | None = Field(None, max_length=50, description="Type category")


class IncomeInfo(BaseModel):
    """All income information for tax estimate."""

    wages: list[WageIncomeInfo] | None = Field(None, description="W-2 wage income")
    interest: InterestIncomeInfo | None = Field(None, description="Interest income")
    dividends: DividendIncomeInfo | None = Field(None, description="Dividend income")
    capital_gains: CapitalGainsInfo | None = Field(None, description="Capital gains/losses")
    equity_compensation: list[EquityCompensationInfo] | None = Field(None, description="Equity comp")
    self_employment: list[SelfEmploymentInfo] | None = Field(None, description="Self-employment")
    rental_income: list[RentalIncomeInfo] | None = Field(None, description="Rental income")
    retirement: RetirementIncomeInfo | None = Field(None, description="Retirement income")
    other_income: list[OtherIncomeInfo] | None = Field(None, description="Other income")


# =============================================================================
# Request Models - Adjustments and Deductions
# =============================================================================


class AdjustmentsInfo(BaseModel):
    """Above-the-line adjustments to income."""

    hsa_contribution: Decimal = Field(default=Decimal(0), ge=0, description="HSA contributions")
    ira_contribution: Decimal = Field(default=Decimal(0), ge=0, description="IRA contributions")
    student_loan_interest: Decimal = Field(default=Decimal(0), ge=0, description="Student loan interest")
    educator_expenses: Decimal = Field(default=Decimal(0), ge=0, description="Educator expenses")
    self_employment_health_insurance: Decimal = Field(
        default=Decimal(0), ge=0, description="SE health insurance"
    )
    self_employment_tax_deduction: Decimal | None = Field(
        None, ge=0, description="SE tax deduction (calculated)"
    )
    alimony_paid: Decimal = Field(default=Decimal(0), ge=0, description="Alimony paid")
    alimony_paid_pre_2019: bool = Field(
        default=False, description="Divorce was before 2019"
    )


class ItemizedDeductionsInfo(BaseModel):
    """Itemized deduction amounts."""

    medical_expenses: Decimal = Field(default=Decimal(0), ge=0, description="Medical expenses")
    state_local_taxes_paid: Decimal = Field(default=Decimal(0), ge=0, description="SALT paid")
    real_estate_taxes: Decimal = Field(default=Decimal(0), ge=0, description="Property taxes")
    personal_property_taxes: Decimal = Field(default=Decimal(0), ge=0, description="Personal property")
    mortgage_interest: Decimal = Field(default=Decimal(0), ge=0, description="Mortgage interest")
    mortgage_points: Decimal = Field(default=Decimal(0), ge=0, description="Mortgage points")
    charitable_cash: Decimal = Field(default=Decimal(0), ge=0, description="Cash charity")
    charitable_noncash: Decimal = Field(default=Decimal(0), ge=0, description="Non-cash charity")
    casualty_loss: Decimal = Field(default=Decimal(0), ge=0, description="Casualty losses")
    gambling_losses: Decimal = Field(default=Decimal(0), ge=0, description="Gambling losses")
    other_itemized: Decimal = Field(default=Decimal(0), ge=0, description="Other itemized")


class DeductionsInfo(BaseModel):
    """Deduction preferences."""

    type: Literal["standard", "itemized"] = Field(..., description="Deduction type preference")
    itemized: ItemizedDeductionsInfo | None = Field(None, description="Itemized amounts")


# =============================================================================
# Request Models - Credits and Withholding
# =============================================================================


class ChildTaxCreditInfo(BaseModel):
    """Child Tax Credit information."""

    eligible_children_under_17: int = Field(default=0, ge=0, description="Children under 17")
    eligible_children_17_plus: int = Field(default=0, ge=0, description="Other dependents")


class ChildDependentCareInfo(BaseModel):
    """Child and Dependent Care Credit."""

    expenses_paid: Decimal = Field(default=Decimal(0), ge=0, description="Care expenses paid")
    qualifying_persons: int = Field(default=0, ge=0, le=2, description="Qualifying persons (0-2)")


class EducationCreditInfo(BaseModel):
    """Education credits (AOTC, LLC)."""

    aotc_eligible_students: int = Field(default=0, ge=0, description="AOTC eligible students")
    aotc_expenses: Decimal = Field(default=Decimal(0), ge=0, description="AOTC expenses")
    llc_expenses: Decimal = Field(default=Decimal(0), ge=0, description="LLC expenses")


class EarnedIncomeCreditInfo(BaseModel):
    """Earned Income Credit."""

    claim_eic: bool = Field(default=False, description="Claiming EIC")
    investment_income: Decimal = Field(default=Decimal(0), ge=0, description="Investment income")


class SaversCreditInfo(BaseModel):
    """Saver's Credit."""

    retirement_contributions: Decimal = Field(default=Decimal(0), ge=0, description="Contributions")


class ForeignTaxCreditInfo(BaseModel):
    """Foreign Tax Credit."""

    foreign_taxes_paid: Decimal = Field(default=Decimal(0), ge=0, description="Foreign taxes paid")


class CreditsInfo(BaseModel):
    """Tax credit information."""

    child_tax_credit: ChildTaxCreditInfo | None = Field(None, description="CTC")
    child_dependent_care: ChildDependentCareInfo | None = Field(None, description="CDCC")
    education: EducationCreditInfo | None = Field(None, description="Education credits")
    earned_income_credit: EarnedIncomeCreditInfo | None = Field(None, description="EIC")
    savers_credit: SaversCreditInfo | None = Field(None, description="Saver's Credit")
    foreign_tax_credit: ForeignTaxCreditInfo | None = Field(None, description="FTC")
    estimated_payments: Decimal = Field(default=Decimal(0), ge=0, description="Est. payments")


class EstimatedPaymentInfo(BaseModel):
    """Estimated tax payment record."""

    date: str = Field(..., description="Payment date")
    amount: Decimal = Field(..., ge=0, description="Payment amount")


class StateEstimatedPaymentInfo(BaseModel):
    """State estimated tax payment."""

    state: str = Field(..., description="State code")
    date: str = Field(..., description="Payment date")
    amount: Decimal = Field(..., ge=0, description="Payment amount")


class PriorYearOverpaymentInfo(BaseModel):
    """Prior year overpayment applied."""

    federal: Decimal = Field(default=Decimal(0), ge=0, description="Federal applied")
    state: dict[str, Decimal] | None = Field(None, description="State amounts by code")


class WithholdingInfo(BaseModel):
    """Withholding and payment information."""

    federal_estimated_payments: list[EstimatedPaymentInfo] | None = Field(None, description="Federal est. payments")
    state_estimated_payments: list[StateEstimatedPaymentInfo] | None = Field(None, description="State est. payments")
    prior_year_overpayment_applied: PriorYearOverpaymentInfo | None = Field(None, description="Prior year applied")


# =============================================================================
# Request Models - Options and Main Request
# =============================================================================


class CalculationOptions(BaseModel):
    """Options for calculation behavior."""

    optimize_deduction: bool = Field(default=True, description="Auto-choose standard vs itemized")
    include_trace: bool = Field(default=False, description="Include calculation trace")
    trace_verbosity: Literal["minimal", "standard", "detailed"] = Field(
        default="standard", description="Trace detail level"
    )


class EstimateRequest(BaseModel):
    """
    Complete request for creating a tax estimate.

    This is the main API request model for POST /v1/estimates.
    """

    tax_year: int = Field(..., ge=2024, le=2025, description="Tax year (2024 or 2025)")
    save: bool = Field(default=False, description="Save estimate (requires auth)")

    filer: FilerInfo = Field(..., description="Filer information")
    spouse: SpouseInfo | None = Field(None, description="Spouse information")
    dependents: list[DependentInfo] | None = Field(None, description="Dependents")

    residency: ResidencyInfo = Field(..., description="Residency information")
    income: IncomeInfo = Field(..., description="Income information")

    adjustments: AdjustmentsInfo | None = Field(None, description="Adjustments to income")
    deductions: DeductionsInfo | None = Field(None, description="Deduction preferences")
    credits: CreditsInfo | None = Field(None, description="Credit information")
    withholding: WithholdingInfo | None = Field(None, description="Withholding information")

    options: CalculationOptions | None = Field(None, description="Calculation options")


# =============================================================================
# Response Models
# =============================================================================


class WarningInfo(BaseModel):
    """Warning information in responses."""

    code: str = Field(..., description="Warning code")
    severity: WarningSeverity = Field(..., description="Severity level")
    message: str = Field(..., description="Warning message")
    field: str | None = Field(None, description="Related field")
    jurisdiction: str | None = Field(None, description="Related jurisdiction")


class BracketBreakdownInfo(BaseModel):
    """Tax bracket breakdown in response."""

    bracket_min: Decimal = Field(..., description="Bracket lower bound")
    bracket_max: Decimal | None = Field(None, description="Bracket upper bound")
    rate: Decimal = Field(..., description="Tax rate")
    income_in_bracket: Decimal = Field(..., description="Income taxed in bracket")
    tax_in_bracket: Decimal = Field(..., description="Tax for this bracket")


class CreditBreakdownInfo(BaseModel):
    """Credit breakdown in response."""

    code: str = Field(..., description="Credit code")
    name: str = Field(..., description="Credit name")
    amount: Decimal = Field(..., description="Credit amount")
    refundable: bool = Field(..., description="Whether refundable")
    limited_to: Decimal | None = Field(None, description="Amount limited to")
    phase_out_applied: bool = Field(default=False, description="Phase-out applied")


class AdjustmentItemInfo(BaseModel):
    """State adjustment item."""

    code: str = Field(..., description="Adjustment code")
    description: str = Field(..., description="Description")
    amount: Decimal = Field(..., description="Amount")


class EstimateSummary(BaseModel):
    """Summary of tax estimate results."""

    total_income: Decimal = Field(..., description="Total gross income")
    adjusted_gross_income: Decimal = Field(..., description="AGI")
    taxable_income: Decimal = Field(..., description="Taxable income")

    total_federal_tax: Decimal = Field(..., description="Total federal tax")
    total_state_tax: Decimal = Field(default=Decimal(0), description="Total state tax")
    total_local_tax: Decimal = Field(default=Decimal(0), description="Total local tax")
    total_fica_tax: Decimal = Field(default=Decimal(0), description="Total FICA tax")
    total_tax: Decimal = Field(..., description="Total tax liability")

    effective_rate: Decimal = Field(..., description="Effective tax rate")
    marginal_rate: Decimal = Field(..., description="Marginal tax rate")

    total_withholding: Decimal = Field(default=Decimal(0), description="Total withheld")
    total_estimated_payments: Decimal = Field(default=Decimal(0), description="Est. payments made")
    total_credits: Decimal = Field(default=Decimal(0), description="Total credits")

    balance_due: Decimal = Field(..., description="Amount owed (positive) or refund (negative)")
    refund_amount: Decimal = Field(default=Decimal(0), description="Refund if applicable")


class FederalTaxResultInfo(BaseModel):
    """Federal tax calculation result for API response."""

    jurisdiction_id: Literal["US"] = Field(default="US")

    gross_income: Decimal = Field(..., description="Gross income")
    adjustments: Decimal = Field(default=Decimal(0), description="Total adjustments")
    adjusted_gross_income: Decimal = Field(..., description="AGI")

    deduction_type: Literal["standard", "itemized"] = Field(..., description="Deduction method")
    deduction_amount: Decimal = Field(..., description="Deduction amount used")
    qualified_business_income_deduction: Decimal | None = Field(None, description="QBI deduction")

    taxable_income: Decimal = Field(..., description="Taxable income")

    tax_before_credits: Decimal = Field(..., description="Tax before credits")
    bracket_breakdown: list[BracketBreakdownInfo] = Field(default_factory=list)

    nonrefundable_credits: list[CreditBreakdownInfo] = Field(default_factory=list)
    total_nonrefundable_credits: Decimal = Field(default=Decimal(0))
    tax_after_nonrefundable_credits: Decimal = Field(default=Decimal(0))

    refundable_credits: list[CreditBreakdownInfo] = Field(default_factory=list)
    total_refundable_credits: Decimal = Field(default=Decimal(0))

    self_employment_tax: Decimal = Field(default=Decimal(0))
    additional_medicare_tax: Decimal = Field(default=Decimal(0))
    net_investment_income_tax: Decimal = Field(default=Decimal(0))
    other_taxes: Decimal = Field(default=Decimal(0))

    total_tax: Decimal = Field(..., description="Total tax liability")

    withholding: Decimal = Field(default=Decimal(0))
    estimated_payments: Decimal = Field(default=Decimal(0))
    total_payments: Decimal = Field(default=Decimal(0))

    balance_due_or_refund: Decimal = Field(..., description="Balance due/refund")


class StateTaxResultInfo(BaseModel):
    """State tax calculation result for API response."""

    jurisdiction_id: str = Field(..., description="State jurisdiction ID (e.g., US-CA)")
    jurisdiction_name: str = Field(..., description="State name")

    residency_status: Literal["full_year", "part_year", "nonresident"] = Field(
        default="full_year", description="Residency status"
    )

    federal_agi: Decimal = Field(default=Decimal(0), description="Federal AGI")
    state_additions: list[AdjustmentItemInfo] = Field(default_factory=list)
    state_subtractions: list[AdjustmentItemInfo] = Field(default_factory=list)
    state_agi: Decimal = Field(default=Decimal(0), description="State AGI")

    deduction_type: Literal["standard", "itemized"] = Field(default="standard")
    deduction_amount: Decimal = Field(default=Decimal(0))

    exemptions: int = Field(default=0, description="Number of exemptions")
    exemption_amount: Decimal = Field(default=Decimal(0))

    taxable_income: Decimal = Field(..., description="State taxable income")

    tax_before_credits: Decimal = Field(..., description="Tax before credits")
    bracket_breakdown: list[BracketBreakdownInfo] | None = Field(None)

    credits: list[CreditBreakdownInfo] = Field(default_factory=list)
    other_state_tax_credit: Decimal = Field(default=Decimal(0))
    total_credits: Decimal = Field(default=Decimal(0))

    total_tax: Decimal = Field(..., description="Total state tax")

    withholding: Decimal = Field(default=Decimal(0))
    estimated_payments: Decimal = Field(default=Decimal(0))

    balance_due_or_refund: Decimal = Field(..., description="Balance due/refund")


class LocalTaxResultInfo(BaseModel):
    """Local tax calculation result for API response."""

    jurisdiction_id: str = Field(..., description="Local jurisdiction ID")
    jurisdiction_name: str = Field(..., description="Local jurisdiction name")
    tax_type: str = Field(..., description="Type of local tax")

    taxpayer_status: Literal["resident", "nonresident", "both"] = Field(
        default="resident", description="Taxpayer status"
    )

    taxable_income: Decimal = Field(..., description="Taxable income")
    rate: Decimal = Field(..., description="Tax rate")
    tax_before_credits: Decimal = Field(..., description="Tax before credits")

    credits: list[CreditBreakdownInfo] = Field(default_factory=list)
    total_credits: Decimal = Field(default=Decimal(0))

    total_tax: Decimal = Field(..., description="Total local tax")
    withholding: Decimal = Field(default=Decimal(0))
    balance_due_or_refund: Decimal = Field(..., description="Balance due/refund")


class TraceStageInfo(BaseModel):
    """Stage information in calculation trace."""

    stage_id: str = Field(..., description="Stage identifier")
    stage_name: str = Field(..., description="Stage name")
    jurisdiction: str | None = Field(None, description="Related jurisdiction")
    inputs: dict[str, Any] = Field(default_factory=dict)
    calculations: list[dict[str, Any]] = Field(default_factory=list)
    outputs: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] | None = Field(None)


class CalculationTraceInfo(BaseModel):
    """Calculation trace for debugging and transparency."""

    version: str = Field(default="1.0.0", description="Trace format version")
    generated_at: datetime = Field(..., description="When trace was generated")
    stages: list[TraceStageInfo] = Field(default_factory=list)
    performance: dict[str, Any] | None = Field(None, description="Performance metrics")


class LinksInfo(BaseModel):
    """HATEOAS links in response."""

    self: str = Field(..., description="Self link")
    update: str | None = Field(None, description="Update link")
    delete: str | None = Field(None, description="Delete link")
    pdf: str | None = Field(None, description="PDF export link")
    compare: str | None = Field(None, description="Compare link")


class EstimateResponse(BaseModel):
    """
    Complete response for a tax estimate.

    This is the main API response model for POST /v1/estimates.
    """

    id: str = Field(..., description="Estimate ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime | None = Field(None, description="Last update timestamp")
    tax_year: int = Field(..., description="Tax year")
    status: EstimateStatus = Field(..., description="Calculation status")
    rules_version: str = Field(default="1.0.0", description="Rules version used")

    summary: EstimateSummary = Field(..., description="Result summary")

    federal: FederalTaxResultInfo = Field(..., description="Federal tax result")
    states: list[StateTaxResultInfo] = Field(default_factory=list, description="State results")
    local: list[LocalTaxResultInfo] = Field(default_factory=list, description="Local results")

    trace: CalculationTraceInfo | None = Field(None, description="Calculation trace")

    warnings: list[WarningInfo] = Field(default_factory=list, description="Warnings")
    disclaimers: list[str] = Field(
        default_factory=lambda: [
            "This is an estimate only and should not be considered tax advice.",
            "Consult a qualified tax professional for your specific situation.",
            "Tax laws change frequently; verify all calculations with official sources.",
        ]
    )

    links: LinksInfo | None = Field(None, description="HATEOAS links")


# =============================================================================
# Jurisdiction Response Models
# =============================================================================


class JurisdictionSummary(BaseModel):
    """Summary of a jurisdiction for listing."""

    id: str = Field(..., description="Jurisdiction ID")
    name: str = Field(..., description="Jurisdiction name")
    level: JurisdictionLevel = Field(..., description="Jurisdiction level")
    parent_id: str | None = Field(None, description="Parent jurisdiction ID")
    has_income_tax: bool = Field(..., description="Has income tax")
    tax_type: str | None = Field(None, description="Tax type (progressive, flat, none)")
    max_rate: Decimal | None = Field(None, description="Maximum tax rate")
    links: dict[str, str] | None = Field(None, description="Related links")


class TaxSummaryInfo(BaseModel):
    """Tax summary for a jurisdiction."""

    type: str = Field(..., description="Tax type")
    brackets_count: int = Field(default=0, description="Number of brackets")
    min_rate: Decimal = Field(default=Decimal(0), description="Minimum rate")
    max_rate: Decimal = Field(default=Decimal(0), description="Maximum rate")
    standard_deduction: dict[str, Decimal] | None = Field(None, description="Standard deductions by status")


class ResidencyRulesInfo(BaseModel):
    """Residency rules for a jurisdiction."""

    full_year_threshold_days: int | None = Field(None, description="Days for full-year resident")
    part_year_available: bool = Field(default=True, description="Part-year filing available")
    statutory_resident_rule: bool = Field(default=False, description="Has statutory resident rule")


class LocalTaxesInfo(BaseModel):
    """Local tax information for a state."""

    has_local_income_tax: bool = Field(..., description="Has local income taxes")


class JurisdictionDetails(BaseModel):
    """Detailed jurisdiction information."""

    id: str = Field(..., description="Jurisdiction ID")
    name: str = Field(..., description="Short name")
    full_name: str = Field(..., description="Full official name")
    level: JurisdictionLevel = Field(..., description="Jurisdiction level")
    parent_id: str | None = Field(None, description="Parent jurisdiction ID")
    has_income_tax: bool = Field(..., description="Has income tax")
    tax_year: int = Field(..., description="Tax year for data")

    tax_summary: TaxSummaryInfo | None = Field(None, description="Tax summary")
    residency_rules: ResidencyRulesInfo | None = Field(None, description="Residency rules")
    reciprocity: list[str] = Field(default_factory=list, description="Reciprocity states")
    local_taxes: LocalTaxesInfo | None = Field(None, description="Local tax info")

    children: list[JurisdictionSummary] = Field(default_factory=list, description="Child jurisdictions")
    links: dict[str, str] | None = Field(None, description="Related links")


class BracketInfo(BaseModel):
    """Tax bracket information."""

    min: Decimal = Field(..., description="Bracket minimum")
    max: Decimal | None = Field(None, description="Bracket maximum")
    rate: Decimal = Field(..., description="Tax rate")


class BracketsResponse(BaseModel):
    """Response for tax brackets endpoint."""

    jurisdiction_id: str = Field(..., description="Jurisdiction ID")
    tax_year: int = Field(..., description="Tax year")
    brackets_by_filing_status: dict[str, list[BracketInfo]] = Field(
        default_factory=dict, description="Brackets by filing status"
    )


class JurisdictionListResponse(BaseModel):
    """Response for listing jurisdictions."""

    data: list[JurisdictionSummary] = Field(..., description="Jurisdiction list")
    pagination: dict[str, Any] = Field(..., description="Pagination info")


# =============================================================================
# Tax Year Response Models
# =============================================================================


class TaxYearSummary(BaseModel):
    """Summary of a tax year."""

    year: int = Field(..., description="Tax year")
    status: Literal["current", "prior", "upcoming"] = Field(..., description="Year status")
    filing_deadline: str = Field(..., description="Filing deadline date")
    extension_deadline: str | None = Field(None, description="Extension deadline")
    rules_version: str = Field(..., description="Rules version")
    last_updated: datetime | None = Field(None, description="Last update time")


class KeyThresholdsInfo(BaseModel):
    """Key tax thresholds for a year."""

    model_config = {"populate_by_name": True}

    standard_deduction: dict[str, Decimal] = Field(..., description="Standard deduction by status")
    social_security_wage_base: Decimal = Field(..., description="SS wage base")
    limit_401k: Decimal = Field(..., serialization_alias="401k_limit", description="401k contribution limit")
    ira_limit: Decimal = Field(..., description="IRA contribution limit")


class TaxYearDetails(BaseModel):
    """Detailed tax year information."""

    year: int = Field(..., description="Tax year")
    status: str = Field(..., description="Year status")
    filing_deadline: str = Field(..., description="Filing deadline")
    extension_deadline: str | None = Field(None, description="Extension deadline")
    rules_version: str = Field(..., description="Rules version")
    last_updated: datetime | None = Field(None, description="Last update")

    key_thresholds: KeyThresholdsInfo | None = Field(None, description="Key thresholds")
    supported_jurisdictions: dict[str, int] | None = Field(None, description="Supported jurisdictions count")
    changelog: list[dict[str, Any]] | None = Field(None, description="Change history")


class TaxYearListResponse(BaseModel):
    """Response for listing tax years."""

    data: list[TaxYearSummary] = Field(..., description="Tax year list")
    default_year: int = Field(..., description="Default/current year")


# =============================================================================
# Validation Response Models
# =============================================================================


class ValidationErrorInfo(BaseModel):
    """Validation error detail."""

    field: str = Field(..., description="Field path")
    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    value: Any | None = Field(None, description="Invalid value")


class SuggestionInfo(BaseModel):
    """Suggestion for improving input."""

    field: str = Field(..., description="Field path")
    code: str = Field(..., description="Suggestion code")
    message: str = Field(..., description="Suggestion message")


class ValidationResponse(BaseModel):
    """Response for validation endpoint."""

    valid: bool = Field(..., description="Whether input is valid")
    errors: list[ValidationErrorInfo] = Field(default_factory=list, description="Validation errors")
    warnings: list[WarningInfo] = Field(default_factory=list, description="Warnings")
    suggestions: list[SuggestionInfo] = Field(default_factory=list, description="Suggestions")


class StandardizedAddress(BaseModel):
    """Standardized address from validation."""

    street: str = Field(..., description="Street address")
    city: str = Field(..., description="City")
    state: str = Field(..., description="State code")
    zip: str = Field(..., description="ZIP code")
    formatted: str = Field(..., description="Formatted address string")


class JurisdictionLookupInfo(BaseModel):
    """Jurisdiction lookup from address."""

    state: str | None = Field(None, description="State jurisdiction ID")
    county: str | None = Field(None, description="County jurisdiction ID")
    city: str | None = Field(None, description="City jurisdiction ID")
    borough: str | None = Field(None, description="Borough (NYC)")


class AddressValidationResponse(BaseModel):
    """Response for address validation."""

    valid: bool = Field(..., description="Whether address is valid")
    standardized: StandardizedAddress | None = Field(None, description="Standardized address")
    jurisdiction_lookup: JurisdictionLookupInfo | None = Field(None, description="Jurisdictions")
