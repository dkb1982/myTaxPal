"""
Pydantic models for international tax calculation input and output.

These models define the structure of user input and calculation results
for international tax calculations (non-US jurisdictions).

All monetary values use Decimal for precision.
"""

from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from tax_estimator.rules.schema import CountryCode, CurrencyCode


# =============================================================================
# Country to Currency Mapping
# =============================================================================

COUNTRY_CURRENCY_MAP: dict[str, str] = {
    "US": "USD",
    "GB": "GBP",
    "DE": "EUR",
    "FR": "EUR",
    "SG": "SGD",
    "HK": "HKD",
    "AE": "AED",
    "JP": "JPY",
    "AU": "AUD",
    "CA": "CAD",
    "IT": "EUR",
    "ES": "EUR",
    "PT": "EUR",
}


def get_currency_for_country(country_code: str) -> str:
    """Get the default currency code for a country."""
    return COUNTRY_CURRENCY_MAP.get(country_code, "USD")


# =============================================================================
# UK-Specific Input Models
# =============================================================================


class UKTaxRegion(str, Enum):
    """UK tax regions (Scotland has different income tax rates)."""

    ENGLAND = "england"
    WALES = "wales"
    SCOTLAND = "scotland"
    NORTHERN_IRELAND = "northern_ireland"


class UKNICategory(str, Enum):
    """UK National Insurance category letters."""

    A = "A"  # Standard
    B = "B"  # Married women reduced rate
    C = "C"  # Over state pension age
    H = "H"  # Apprentice under 25
    J = "J"  # Deferred (second job)
    M = "M"  # Under 21
    Z = "Z"  # Under 21 deferred


class UKStudentLoanPlanType(str, Enum):
    """UK student loan repayment plan types."""

    NONE = "none"
    PLAN_1 = "plan_1"
    PLAN_2 = "plan_2"
    PLAN_4 = "plan_4"
    PLAN_5 = "plan_5"
    POSTGRAD = "postgrad_only"


class UKTaxInput(BaseModel):
    """UK-specific tax input fields."""

    tax_region: UKTaxRegion = Field(
        default=UKTaxRegion.ENGLAND,
        description="Which part of the UK (Scotland has different rates)"
    )
    tax_code: str | None = Field(
        None,
        description="Tax code from payslip (e.g., 1257L)"
    )
    ni_category: UKNICategory = Field(
        default=UKNICategory.A,
        description="National Insurance category letter"
    )
    student_loan_plan: UKStudentLoanPlanType = Field(
        default=UKStudentLoanPlanType.NONE,
        description="Student loan repayment plan"
    )
    has_postgrad_loan: bool = Field(
        default=False,
        description="Has postgraduate loan"
    )

    # Income fields
    employment_income: Decimal = Field(
        default=Decimal(0), ge=0,
        description="Gross employment income (salary)"
    )
    self_employment_income: Decimal = Field(
        default=Decimal(0), ge=0,
        description="Net self-employment profit"
    )
    savings_interest: Decimal = Field(
        default=Decimal(0), ge=0,
        description="Interest from savings"
    )
    dividend_income: Decimal = Field(
        default=Decimal(0), ge=0,
        description="Dividend income"
    )
    rental_income: Decimal = Field(
        default=Decimal(0), ge=0,
        description="Net rental income"
    )
    pension_income: Decimal = Field(
        default=Decimal(0), ge=0,
        description="Pension income"
    )
    other_income: Decimal = Field(
        default=Decimal(0), ge=0,
        description="Other taxable income"
    )

    # Deductions
    pension_contributions: Decimal = Field(
        default=Decimal(0), ge=0,
        description="Pension contributions (relief at source)"
    )
    gift_aid_donations: Decimal = Field(
        default=Decimal(0), ge=0,
        description="Gift Aid charitable donations"
    )

    # Withholding
    paye_deducted: Decimal = Field(
        default=Decimal(0), ge=0,
        description="Income tax already deducted by employer"
    )
    ni_deducted: Decimal = Field(
        default=Decimal(0), ge=0,
        description="National Insurance already deducted"
    )


# =============================================================================
# Germany-Specific Input Models
# =============================================================================


class DETaxClass(str, Enum):
    """German tax classes (Steuerklassen)."""

    I = "I"    # Single, divorced, widowed
    II = "II"   # Single parent
    III = "III"  # Married (higher earner)
    IV = "IV"   # Married (equal earners)
    V = "V"    # Married (lower earner)
    VI = "VI"   # Second job


class DETaxInput(BaseModel):
    """Germany-specific tax input fields."""

    tax_class: DETaxClass = Field(
        default=DETaxClass.I,
        description="Steuerklasse (tax class)"
    )
    has_church_membership: bool = Field(
        default=False,
        description="Member of taxable church (Kirchensteuer)"
    )
    state: str | None = Field(
        None,
        description="Federal state (for church tax rate 8% or 9%)"
    )
    num_children: int = Field(
        default=0, ge=0,
        description="Number of children (Kinderfreibetrag)"
    )

    # Income
    employment_income: Decimal = Field(
        default=Decimal(0), ge=0,
        description="Gross employment income"
    )
    self_employment_income: Decimal = Field(
        default=Decimal(0), ge=0,
        description="Self-employment income"
    )
    capital_income: Decimal = Field(
        default=Decimal(0), ge=0,
        description="Capital gains and investment income"
    )
    other_income: Decimal = Field(
        default=Decimal(0), ge=0,
        description="Other taxable income"
    )

    # Deductions (Werbungskosten)
    work_expenses: Decimal = Field(
        default=Decimal(0), ge=0,
        description="Work-related expenses"
    )
    commuting_distance_km: Decimal = Field(
        default=Decimal(0), ge=0,
        description="Daily commuting distance in km"
    )
    home_office_days: int = Field(
        default=0, ge=0, le=365,
        description="Days worked from home"
    )


# =============================================================================
# France-Specific Input Models
# =============================================================================


class FRTaxInput(BaseModel):
    """France-specific tax input fields."""

    is_married: bool = Field(
        default=False,
        description="Married or PACS"
    )
    num_children: int = Field(
        default=0, ge=0,
        description="Number of dependent children"
    )
    is_single_parent: bool = Field(
        default=False,
        description="Single parent status"
    )

    # Income
    employment_income: Decimal = Field(
        default=Decimal(0), ge=0,
        description="Gross employment income (salaire brut)"
    )
    self_employment_income: Decimal = Field(
        default=Decimal(0), ge=0,
        description="Self-employment income"
    )
    investment_income: Decimal = Field(
        default=Decimal(0), ge=0,
        description="Investment income"
    )
    rental_income: Decimal = Field(
        default=Decimal(0), ge=0,
        description="Rental income (revenus fonciers)"
    )

    # Deductions
    use_frais_reels: bool = Field(
        default=False,
        description="Use actual expenses instead of 10% standard deduction"
    )
    frais_reels_amount: Decimal = Field(
        default=Decimal(0), ge=0,
        description="Actual work expenses if using frais reels"
    )


# =============================================================================
# Singapore-Specific Input Models
# =============================================================================


class SGResidentStatus(str, Enum):
    """Singapore tax residency status."""

    RESIDENT = "resident"
    NON_RESIDENT = "non_resident"


class SGTaxInput(BaseModel):
    """Singapore-specific tax input fields."""

    resident_status: SGResidentStatus = Field(
        default=SGResidentStatus.RESIDENT,
        description="Tax residency status (183+ days = resident)"
    )
    age: int = Field(
        default=35, ge=0, le=120,
        description="Age (affects CPF rates). Defaults to 35 if not provided."
    )
    is_citizen_or_pr: bool = Field(
        default=True,
        description="Singapore citizen or permanent resident (for CPF)"
    )

    # Income
    employment_income: Decimal = Field(
        default=Decimal(0), ge=0,
        description="Gross employment income"
    )
    bonus_income: Decimal = Field(
        default=Decimal(0), ge=0,
        description="Annual bonus (Additional Wage)"
    )
    other_income: Decimal = Field(
        default=Decimal(0), ge=0,
        description="Other taxable income"
    )

    # Reliefs
    cpf_relief: Decimal = Field(
        default=Decimal(0), ge=0,
        description="CPF relief (usually auto-calculated)"
    )
    course_fees_relief: Decimal = Field(
        default=Decimal(0), ge=0,
        description="Course fees relief"
    )
    life_insurance_relief: Decimal = Field(
        default=Decimal(0), ge=0,
        description="Life insurance relief"
    )


# =============================================================================
# Hong Kong-Specific Input Models
# =============================================================================


class HKTaxInput(BaseModel):
    """Hong Kong-specific tax input fields."""

    is_married: bool = Field(
        default=False,
        description="Married person's allowance"
    )
    num_children: int = Field(
        default=0, ge=0,
        description="Number of children"
    )
    has_dependent_parent: bool = Field(
        default=False,
        description="Has dependent parent/grandparent"
    )
    is_single_parent: bool = Field(
        default=False,
        description="Single parent allowance"
    )

    # Income
    employment_income: Decimal = Field(
        default=Decimal(0), ge=0,
        description="Total employment income"
    )
    other_income: Decimal = Field(
        default=Decimal(0), ge=0,
        description="Other income"
    )

    # MPF already deducted
    mpf_deducted: Decimal = Field(
        default=Decimal(0), ge=0,
        description="MPF contributions already deducted"
    )


# =============================================================================
# UAE-Specific Input Models (No Income Tax)
# =============================================================================


class AETaxInput(BaseModel):
    """UAE-specific input fields (no income tax applies)."""

    employment_income: Decimal = Field(
        default=Decimal(0), ge=0,
        description="Gross employment income (no tax)"
    )
    other_income: Decimal = Field(
        default=Decimal(0), ge=0,
        description="Other income (no tax)"
    )

    # Note: UAE has no personal income tax
    # This model exists for comparison purposes


# =============================================================================
# Japan-Specific Input Models
# =============================================================================


class JPAgeCategory(str, Enum):
    """Japan age categories (affect social insurance)."""

    UNDER_40 = "under_40"
    AGE_40_TO_64 = "40_to_64"  # Long-term care insurance applies
    AGE_65_TO_69 = "65_to_69"
    AGE_70_PLUS = "70_plus"


class JPTaxInput(BaseModel):
    """Japan-specific tax input fields."""

    age_category: JPAgeCategory = Field(
        default=JPAgeCategory.UNDER_40,
        description="Age category (affects social insurance)"
    )
    prefecture: str | None = Field(
        None,
        description="Prefecture of residence (for resident tax)"
    )
    num_dependents: int = Field(
        default=0, ge=0,
        description="Number of dependents"
    )
    has_spouse: bool = Field(
        default=False,
        description="Has spouse (spouse deduction)"
    )
    spouse_income: Decimal = Field(
        default=Decimal(0), ge=0,
        description="Spouse's income (affects deduction eligibility)"
    )

    # Income
    employment_income: Decimal = Field(
        default=Decimal(0), ge=0,
        description="Employment income (Kyuyo Shotoku)"
    )
    bonus_income: Decimal = Field(
        default=Decimal(0), ge=0,
        description="Bonus income"
    )
    business_income: Decimal = Field(
        default=Decimal(0), ge=0,
        description="Business income (Jigyou Shotoku)"
    )
    miscellaneous_income: Decimal = Field(
        default=Decimal(0), ge=0,
        description="Miscellaneous income (Zatsu Shotoku)"
    )

    # Deductions
    social_insurance_paid: Decimal = Field(
        default=Decimal(0), ge=0,
        description="Social insurance already paid"
    )
    life_insurance_premiums: Decimal = Field(
        default=Decimal(0), ge=0,
        description="Life insurance premiums"
    )
    furusato_donations: Decimal = Field(
        default=Decimal(0), ge=0,
        description="Hometown tax donations (Furusato Nozei)"
    )

    # Withholding
    income_tax_withheld: Decimal = Field(
        default=Decimal(0), ge=0,
        description="Income tax already withheld"
    )
    resident_tax_withheld: Decimal = Field(
        default=Decimal(0), ge=0,
        description="Resident tax already withheld"
    )


# =============================================================================
# Australia-Specific Input Models
# =============================================================================


class AUTaxInput(BaseModel):
    """Australia-specific tax input fields."""

    is_resident: bool = Field(
        default=True,
        description="Tax resident of Australia"
    )
    has_private_health: bool = Field(
        default=False,
        description="Has private hospital insurance (avoids MLS)"
    )
    has_help_debt: bool = Field(
        default=False,
        description="Has HELP/HECS student loan debt"
    )

    # Income
    employment_income: Decimal = Field(
        default=Decimal(0), ge=0,
        description="Gross employment income"
    )
    business_income: Decimal = Field(
        default=Decimal(0), ge=0,
        description="Business income"
    )
    investment_income: Decimal = Field(
        default=Decimal(0), ge=0,
        description="Investment income"
    )
    other_income: Decimal = Field(
        default=Decimal(0), ge=0,
        description="Other taxable income"
    )

    # Deductions
    work_deductions: Decimal = Field(
        default=Decimal(0), ge=0,
        description="Work-related deductions"
    )


# =============================================================================
# Canada-Specific Input Models
# =============================================================================


class CATaxInput(BaseModel):
    """Canada-specific tax input fields."""

    province: str = Field(
        default="ON",
        description="Province/territory code (ON, BC, QC, etc.)"
    )

    # Income
    employment_income: Decimal = Field(
        default=Decimal(0), ge=0,
        description="Employment income"
    )
    self_employment_income: Decimal = Field(
        default=Decimal(0), ge=0,
        description="Self-employment income"
    )
    investment_income: Decimal = Field(
        default=Decimal(0), ge=0,
        description="Investment income"
    )
    other_income: Decimal = Field(
        default=Decimal(0), ge=0,
        description="Other income"
    )

    # Deductions
    rrsp_contributions: Decimal = Field(
        default=Decimal(0), ge=0,
        description="RRSP contributions"
    )
    union_dues: Decimal = Field(
        default=Decimal(0), ge=0,
        description="Union/professional dues"
    )


# =============================================================================
# Italy-Specific Input Models
# =============================================================================


class ITTaxInput(BaseModel):
    """Italy-specific tax input fields."""

    region: str | None = Field(
        None,
        description="Region (for addizionale regionale)"
    )
    municipality: str | None = Field(
        None,
        description="Municipality (for addizionale comunale)"
    )
    num_dependents: int = Field(
        default=0, ge=0,
        description="Number of dependents"
    )

    # Income
    employment_income: Decimal = Field(
        default=Decimal(0), ge=0,
        description="Employment income (reddito da lavoro dipendente)"
    )
    self_employment_income: Decimal = Field(
        default=Decimal(0), ge=0,
        description="Self-employment income"
    )
    other_income: Decimal = Field(
        default=Decimal(0), ge=0,
        description="Other income"
    )


# =============================================================================
# Spain-Specific Input Models
# =============================================================================


class ESTaxInput(BaseModel):
    """Spain-specific tax input fields."""

    autonomous_community: str = Field(
        default="madrid",
        description="Autonomous community (affects regional rates)"
    )
    num_dependents: int = Field(
        default=0, ge=0,
        description="Number of dependents"
    )

    # Income
    employment_income: Decimal = Field(
        default=Decimal(0), ge=0,
        description="Employment income (rendimientos del trabajo)"
    )
    self_employment_income: Decimal = Field(
        default=Decimal(0), ge=0,
        description="Self-employment income"
    )
    capital_income: Decimal = Field(
        default=Decimal(0), ge=0,
        description="Capital income"
    )
    other_income: Decimal = Field(
        default=Decimal(0), ge=0,
        description="Other income"
    )


# =============================================================================
# Portugal-Specific Input Models
# =============================================================================


class PTTaxInput(BaseModel):
    """Portugal-specific tax input fields."""

    is_nhr: bool = Field(
        default=False,
        description="Non-Habitual Resident status (if still eligible)"
    )
    is_married: bool = Field(
        default=False,
        description="Married (joint taxation option)"
    )
    num_dependents: int = Field(
        default=0, ge=0,
        description="Number of dependents"
    )

    # Income
    employment_income: Decimal = Field(
        default=Decimal(0), ge=0,
        description="Employment income"
    )
    self_employment_income: Decimal = Field(
        default=Decimal(0), ge=0,
        description="Self-employment income"
    )
    investment_income: Decimal = Field(
        default=Decimal(0), ge=0,
        description="Investment income"
    )
    other_income: Decimal = Field(
        default=Decimal(0), ge=0,
        description="Other income"
    )


# =============================================================================
# Main International Tax Input Model
# =============================================================================


class InternationalTaxInput(BaseModel):
    """
    Complete input for international tax calculation.

    This model combines country selection with country-specific input fields.
    """

    # Required fields
    country_code: str = Field(
        ...,
        description="ISO 3166-1 alpha-2 country code (GB, DE, FR, etc.)"
    )
    tax_year: int = Field(
        ..., ge=2024, le=2030,
        description="Tax year for calculation"
    )

    # Currency (defaults based on country)
    currency_code: str | None = Field(
        None,
        description="ISO 4217 currency code (defaults based on country)"
    )

    # Primary income (common to all countries)
    gross_income: Decimal = Field(
        ..., ge=0,
        description="Primary gross income in local currency"
    )

    # Country-specific input (only one should be populated)
    uk: UKTaxInput | None = Field(None, description="UK-specific input")
    de: DETaxInput | None = Field(None, description="Germany-specific input")
    fr: FRTaxInput | None = Field(None, description="France-specific input")
    sg: SGTaxInput | None = Field(None, description="Singapore-specific input")
    hk: HKTaxInput | None = Field(None, description="Hong Kong-specific input")
    ae: AETaxInput | None = Field(None, description="UAE-specific input")
    jp: JPTaxInput | None = Field(None, description="Japan-specific input")
    au: AUTaxInput | None = Field(None, description="Australia-specific input")
    ca: CATaxInput | None = Field(None, description="Canada-specific input")
    it: ITTaxInput | None = Field(None, description="Italy-specific input")
    es: ESTaxInput | None = Field(None, description="Spain-specific input")
    pt: PTTaxInput | None = Field(None, description="Portugal-specific input")

    @field_validator("country_code")
    @classmethod
    def validate_country_code(cls, v: str) -> str:
        """Ensure country code is uppercase and supported."""
        v = v.upper()
        supported = ["US", "GB", "DE", "FR", "SG", "HK", "AE", "JP", "AU", "CA", "IT", "ES", "PT"]
        if v not in supported:
            raise ValueError(f"Country code {v} not supported. Supported: {', '.join(supported)}")
        return v

    def get_currency(self) -> str:
        """Get the currency code (explicit or default for country)."""
        if self.currency_code:
            return self.currency_code
        return get_currency_for_country(self.country_code)


# =============================================================================
# Tax Component (for breakdown)
# =============================================================================


class TaxComponent(BaseModel):
    """A single component of the tax calculation breakdown."""

    component_id: str = Field(..., description="Unique identifier")
    name: str = Field(..., description="Display name")
    amount: Decimal = Field(..., description="Amount for this component")
    rate: Decimal | None = Field(None, description="Rate applied (if applicable)")
    base: Decimal | None = Field(None, description="Base amount rate was applied to")
    notes: str | None = Field(None, description="Explanatory notes")
    is_deductible: bool = Field(
        default=False,
        description="Whether this is deductible from taxable income"
    )


# =============================================================================
# International Tax Result
# =============================================================================


class InternationalTaxResult(BaseModel):
    """
    Complete result of an international tax calculation.

    All monetary values are in the local currency of the country.
    """

    # Identity
    country_code: str = Field(..., description="Country code")
    country_name: str = Field(..., description="Full country name")
    currency_code: str = Field(..., description="Currency code")
    tax_year: int = Field(..., description="Tax year")

    # Income summary
    gross_income: Decimal = Field(..., description="Total gross income")
    taxable_income: Decimal = Field(..., description="Taxable income after deductions")

    # Tax components
    income_tax: Decimal = Field(
        default=Decimal(0),
        description="Income tax amount"
    )
    social_insurance: Decimal = Field(
        default=Decimal(0),
        description="Social insurance/NI contributions"
    )
    other_taxes: Decimal = Field(
        default=Decimal(0),
        description="Other taxes (surtaxes, local taxes)"
    )
    total_tax: Decimal = Field(..., description="Total tax liability")

    # Net income
    net_income: Decimal = Field(..., description="Net income after all taxes")

    # Rates
    effective_rate: Decimal = Field(
        ...,
        description="Effective tax rate (total_tax / gross_income)"
    )
    marginal_rate: Decimal | None = Field(
        None,
        description="Marginal tax rate"
    )

    # Detailed breakdown
    breakdown: list[TaxComponent] = Field(
        default_factory=list,
        description="Detailed breakdown of tax components"
    )

    # Withholding reconciliation
    total_withheld: Decimal = Field(
        default=Decimal(0),
        description="Total tax already withheld"
    )
    balance_due: Decimal = Field(
        default=Decimal(0),
        description="Additional tax due (negative = refund)"
    )

    # Metadata
    calculation_notes: list[str] = Field(
        default_factory=list,
        description="Notes about the calculation"
    )
    disclaimers: list[str] = Field(
        default_factory=lambda: [
            "This is an estimate only and should not be considered tax advice.",
            "Tax rates and rules are PLACEHOLDER values for development purposes.",
            "Consult a qualified tax professional in your jurisdiction.",
            "Tax laws change frequently; verify all calculations with official sources.",
        ]
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Calculation warnings"
    )


# =============================================================================
# Comparison Result
# =============================================================================


class CountryTaxSummary(BaseModel):
    """Summary of tax for a single country (used in comparisons)."""

    country_code: str = Field(..., description="Country code")
    country_name: str = Field(..., description="Full country name")
    currency_code: str = Field(..., description="Local currency")

    # In local currency
    gross_income_local: Decimal = Field(..., description="Gross income in local currency")
    total_tax_local: Decimal = Field(..., description="Total tax in local currency")
    net_income_local: Decimal = Field(..., description="Net income in local currency")

    # In base currency (for comparison)
    gross_income_base: Decimal = Field(..., description="Gross income in base currency")
    total_tax_base: Decimal = Field(..., description="Total tax in base currency")
    net_income_base: Decimal = Field(..., description="Net income in base currency")

    # Rates
    effective_rate: Decimal = Field(..., description="Effective tax rate")

    # Breakdown
    income_tax_local: Decimal = Field(default=Decimal(0))
    social_insurance_local: Decimal = Field(default=Decimal(0))
    other_taxes_local: Decimal = Field(default=Decimal(0))


class ExchangeRateInfo(BaseModel):
    """Information about exchange rates used in comparison."""

    base_currency: str = Field(..., description="Base currency for comparison")
    rates: dict[str, Decimal] = Field(
        default_factory=dict,
        description="Exchange rates (currency -> rate vs base)"
    )
    rate_date: str = Field(..., description="Date of exchange rates")
    source: str = Field(
        default="PLACEHOLDER - Use official rates",
        description="Source of exchange rates"
    )


class ComparisonResult(BaseModel):
    """
    Result of comparing tax across multiple countries.
    """

    # Base parameters
    base_currency: str = Field(..., description="Currency used for comparison")
    gross_income_base: Decimal = Field(
        ...,
        description="Gross income in base currency"
    )
    tax_year: int = Field(..., description="Tax year")

    # Exchange rates used
    exchange_rates: ExchangeRateInfo = Field(..., description="Exchange rates used")

    # Results by country
    countries: list[CountryTaxSummary] = Field(
        default_factory=list,
        description="Tax summary for each country"
    )

    # Rankings
    lowest_tax_country: str | None = Field(
        None,
        description="Country code with lowest total tax"
    )
    highest_net_income_country: str | None = Field(
        None,
        description="Country code with highest net income"
    )

    # Disclaimers
    disclaimers: list[str] = Field(
        default_factory=lambda: [
            "This comparison is for informational purposes only.",
            "Exchange rates are static placeholders and may not reflect current rates.",
            "Tax systems are complex; this comparison only includes basic income tax.",
            "Consult a tax professional before making relocation decisions.",
            "Living costs, social benefits, and quality of life are not factored in.",
        ]
    )
