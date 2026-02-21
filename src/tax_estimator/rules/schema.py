"""
Pydantic models for tax rule validation.

These models define the schema for jurisdiction tax rules loaded from YAML files.
Based on the jurisdiction rules schema defined in the requirements.

IMPORTANT: Tax values in rule files should be sourced from official government sources
and verified. Do not use placeholder values for production calculations.
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class JurisdictionType(str, Enum):
    """Type of tax jurisdiction."""

    FEDERAL = "federal"
    STATE = "state"
    CITY = "city"
    COUNTY = "county"
    SCHOOL_DISTRICT = "school_district"
    COUNTRY = "country"  # For international jurisdictions


class CountryCode(str, Enum):
    """
    ISO 3166-1 alpha-2 country codes for supported countries.

    IMPORTANT: These are the countries supported for international tax estimation.
    """

    US = "US"  # United States
    GB = "GB"  # United Kingdom
    DE = "DE"  # Germany
    FR = "FR"  # France
    SG = "SG"  # Singapore
    HK = "HK"  # Hong Kong
    AE = "AE"  # United Arab Emirates (Dubai)
    JP = "JP"  # Japan
    AU = "AU"  # Australia
    CA = "CA"  # Canada
    IT = "IT"  # Italy
    ES = "ES"  # Spain
    PT = "PT"  # Portugal


class CurrencyCode(str, Enum):
    """
    ISO 4217 currency codes for supported currencies.
    """

    USD = "USD"  # US Dollar
    GBP = "GBP"  # British Pound Sterling
    EUR = "EUR"  # Euro (Germany, France, Italy, Spain, Portugal)
    SGD = "SGD"  # Singapore Dollar
    HKD = "HKD"  # Hong Kong Dollar
    AED = "AED"  # UAE Dirham
    JPY = "JPY"  # Japanese Yen
    AUD = "AUD"  # Australian Dollar
    CAD = "CAD"  # Canadian Dollar


class TaxYearFormat(str, Enum):
    """How tax year is expressed in different countries."""

    CALENDAR = "calendar"      # Jan 1 - Dec 31 (US, JP, CA, DE, FR, IT, ES, PT, SG)
    UK_FISCAL = "uk_fiscal"    # Apr 6 - Apr 5 (UK)
    AUS_FISCAL = "aus_fiscal"  # Jul 1 - Jun 30 (Australia)
    HK_FISCAL = "hk_fiscal"    # Apr 1 - Mar 31 (Hong Kong)


class FilingStatus(str, Enum):
    """Tax filing status options."""

    SINGLE = "single"
    MFJ = "mfj"  # Married Filing Jointly
    MFS = "mfs"  # Married Filing Separately
    HOH = "hoh"  # Head of Household
    QSS = "qss"  # Qualifying Surviving Spouse


class RateType(str, Enum):
    """How income tax rates are structured."""

    NONE = "none"
    FLAT = "flat"
    GRADUATED = "graduated"


class IncomeTaxType(str, Enum):
    """Type of income tax in the jurisdiction."""

    NONE = "none"
    GRADUATED = "graduated"
    FLAT = "flat"
    INTEREST_DIVIDENDS_ONLY = "interest_dividends_only"
    LOCAL_ONLY = "local_only"


class VerificationStatus(str, Enum):
    """Status of rule verification against authoritative sources."""

    VERIFIED = "verified"
    ASSUMED = "assumed"
    RESEARCH_NEEDED = "research_needed"
    OUTDATED = "outdated"
    PLACEHOLDER = "placeholder"  # For development/testing only


# ============================================================================
# Rate Schedule Models
# ============================================================================


class TaxBracket(BaseModel):
    """A single tax bracket in a graduated tax system."""

    bracket_id: str = Field(..., description="Unique identifier for this bracket")
    filing_status: FilingStatus | Literal["all"] = Field(
        ..., description="Filing status this bracket applies to, or 'all'"
    )
    income_from: float = Field(..., ge=0, description="Lower bound of bracket (inclusive)")
    income_to: float | None = Field(
        None, description="Upper bound of bracket (null = no limit)"
    )
    rate: float = Field(..., ge=0, le=1, description="Tax rate as decimal (e.g., 0.22 = 22%)")
    base_tax: float = Field(
        ..., ge=0, description="Cumulative tax on income below this bracket"
    )

    @field_validator("rate")
    @classmethod
    def validate_rate_is_decimal(cls, v: float) -> float:
        """Ensure rate is expressed as a decimal, not percentage."""
        if v > 1:
            raise ValueError(
                f"Rate {v} appears to be a percentage. Use decimal form (e.g., 0.22 not 22)"
            )
        return v


class Surtax(BaseModel):
    """Additional tax applied above certain income thresholds."""

    surtax_id: str = Field(..., description="Unique identifier for this surtax")
    name: str = Field(..., description="Display name of the surtax")
    threshold: float = Field(..., ge=0, description="Income threshold for surtax to apply")
    rate: float = Field(..., ge=0, le=1, description="Surtax rate as decimal")
    filing_status: FilingStatus | Literal["all"] = Field(
        ..., description="Filing status this surtax applies to"
    )
    description: str = Field(..., description="Explanation of the surtax")


class PreferentialRateThreshold(BaseModel):
    """LTCG / qualified dividend rate thresholds for a filing status."""

    filing_status: str = Field(..., description="Filing status (single, mfj, etc.)")
    zero_rate_limit: float = Field(..., ge=0, description="Income up to which 0% rate applies")
    fifteen_rate_limit: float = Field(..., ge=0, description="Income up to which 15% rate applies (above this: 20%)")


class RateSchedule(BaseModel):
    """Complete rate schedule for a jurisdiction."""

    rate_type: RateType = Field(..., description="Type of rate structure")
    brackets: list[TaxBracket] = Field(
        default_factory=list, description="Tax brackets for graduated tax"
    )
    flat_rate: float | None = Field(None, description="Rate for flat tax jurisdictions")
    surtaxes: list[Surtax] = Field(
        default_factory=list, description="Additional surtaxes"
    )
    preferential_thresholds: list[PreferentialRateThreshold] = Field(
        default_factory=list, description="LTCG/qualified dividend rate thresholds by filing status"
    )

    @field_validator("brackets")
    @classmethod
    def validate_brackets_sorted(cls, v: list[TaxBracket]) -> list[TaxBracket]:
        """Ensure brackets are sorted by income_from within each filing status."""
        if not v:
            return v
        # Group by filing status and verify each group is sorted
        from itertools import groupby

        sorted_brackets = sorted(v, key=lambda b: (str(b.filing_status), b.income_from))
        for status, group in groupby(sorted_brackets, key=lambda b: b.filing_status):
            group_list = list(group)
            incomes = [b.income_from for b in group_list]
            if incomes != sorted(incomes):
                raise ValueError(f"Brackets for {status} are not sorted by income_from")
        return v


# ============================================================================
# Deduction Models
# ============================================================================


class StandardDeductionAmount(BaseModel):
    """Standard deduction amount for a specific filing status."""

    filing_status: FilingStatus = Field(..., description="Filing status")
    amount: float = Field(..., ge=0, description="Standard deduction amount")
    dependent_claimed_elsewhere: float | None = Field(
        None, description="Amount if taxpayer is claimed as dependent"
    )


class AdditionalDeductionAmount(BaseModel):
    """Additional standard deduction for age or blindness."""

    category: Literal["age_65_plus", "blind"] = Field(
        ..., description="Category for additional deduction"
    )
    filing_status: FilingStatus = Field(..., description="Filing status")
    amount: float = Field(..., ge=0, description="Additional deduction amount")


class StandardDeduction(BaseModel):
    """Standard deduction rules for a jurisdiction."""

    available: bool = Field(..., description="Whether standard deduction is available")
    amounts: list[StandardDeductionAmount] = Field(
        default_factory=list, description="Amounts by filing status"
    )
    additional_amounts: list[AdditionalDeductionAmount] = Field(
        default_factory=list, description="Additional amounts for age/blindness"
    )


class ExemptionRules(BaseModel):
    """Personal and dependent exemption rules."""

    personal_exemption_available: bool = Field(
        False, description="Whether personal exemption is available"
    )
    personal_exemption_amount: float = Field(
        0, ge=0, description="Personal exemption amount"
    )
    dependent_exemption_available: bool = Field(
        False, description="Whether dependent exemption is available"
    )
    dependent_exemption_amount: float = Field(
        0, ge=0, description="Dependent exemption amount"
    )


class DeductionRules(BaseModel):
    """All deduction rules for a jurisdiction."""

    standard_deduction: StandardDeduction = Field(
        ..., description="Standard deduction rules"
    )
    exemptions: ExemptionRules = Field(
        default_factory=ExemptionRules, description="Exemption rules"
    )


# ============================================================================
# Payroll Tax Configuration Models
# ============================================================================


class PayrollTaxConfig(BaseModel):
    """Configuration for payroll taxes (Social Security, Medicare)."""

    # Social Security wage base - the maximum earnings subject to SS tax
    social_security_wage_base: float = Field(
        ..., ge=0, description="Maximum earnings subject to Social Security tax"
    )
    # Social Security rate (employee portion)
    social_security_rate: float = Field(
        default=0.062, ge=0, le=1, description="Social Security tax rate (employee portion)"
    )
    # Medicare rate (employee portion)
    medicare_rate: float = Field(
        default=0.0145, ge=0, le=1, description="Medicare tax rate (employee portion)"
    )
    # Additional Medicare tax threshold
    additional_medicare_threshold: float = Field(
        default=200000, ge=0, description="Threshold for additional Medicare tax"
    )
    # Additional Medicare rate
    additional_medicare_rate: float = Field(
        default=0.009, ge=0, le=1, description="Additional Medicare tax rate"
    )
    # Self-employment tax factor (92.35% of net SE income)
    self_employment_factor: float = Field(
        default=0.9235, ge=0, le=1, description="Factor applied to net SE income"
    )
    # NIIT threshold (filing-status specific, not inflation-adjusted)
    niit_threshold_single: float = Field(
        default=200000, ge=0, description="NIIT threshold for Single/HOH"
    )
    niit_threshold_mfj: float = Field(
        default=250000, ge=0, description="NIIT threshold for MFJ/QSS"
    )
    niit_threshold_mfs: float = Field(
        default=125000, ge=0, description="NIIT threshold for MFS"
    )
    # NIIT rate (3.8%)
    niit_rate: float = Field(
        default=0.038, ge=0, le=1, description="Net Investment Income Tax rate"
    )


# ============================================================================
# International Social Insurance Models
# ============================================================================


class SocialInsuranceType(str, Enum):
    """Types of social insurance contributions."""

    PENSION = "pension"
    HEALTH = "health"
    UNEMPLOYMENT = "unemployment"
    LONG_TERM_CARE = "long_term_care"
    WORKERS_COMP = "workers_comp"
    GENERAL_SOCIAL = "general_social"  # UK NI combines multiple purposes


class AgeRestriction(BaseModel):
    """Age restrictions for social insurance contributions."""

    min_age: int | None = Field(None, ge=0, description="Minimum age (inclusive)")
    max_age: int | None = Field(None, ge=0, description="Maximum age (inclusive)")


class SocialInsuranceRateSchedule(BaseModel):
    """Rate schedule for a social insurance component."""

    rate_type: Literal["flat", "banded"] = Field(..., description="Type of rate structure")
    rate: float | None = Field(None, ge=0, le=1, description="Flat rate as decimal")
    brackets: list[TaxBracket] | None = Field(
        None, description="Brackets for banded rates"
    )


class SocialInsuranceComponent(BaseModel):
    """
    A single component of social insurance (e.g., pension, health).

    PLACEHOLDER: Actual rates must be verified from official sources.
    """

    component_id: str = Field(..., description="Unique identifier")
    name: str = Field(..., description="Display name (e.g., 'National Insurance', 'Pension')")
    type: SocialInsuranceType = Field(..., description="Type of social insurance")
    employee_rate: float = Field(
        default=0, ge=0, le=1, description="Employee contribution rate as decimal"
    )
    employer_rate: float = Field(
        default=0, ge=0, le=1, description="Employer contribution rate as decimal"
    )
    ceiling: float | None = Field(
        None, ge=0, description="Maximum earnings subject to contribution"
    )
    floor: float | None = Field(
        None, ge=0, description="Minimum earnings before contribution applies"
    )
    age_restrictions: AgeRestriction | None = Field(
        None, description="Age-based eligibility restrictions"
    )
    notes: str | None = Field(None, description="Additional notes about this component")


class SocialInsuranceRules(BaseModel):
    """
    Complete social insurance rules for a jurisdiction.

    PLACEHOLDER: All rates must be verified from official government sources.
    """

    components: list[SocialInsuranceComponent] = Field(
        default_factory=list, description="Social insurance components"
    )
    calculation_method: Literal["percentage", "banded", "flat"] = Field(
        default="percentage", description="How contributions are calculated"
    )
    employer_contribution: bool = Field(
        default=True, description="Whether employer pays contributions"
    )
    employee_contribution: bool = Field(
        default=True, description="Whether employee pays contributions"
    )


# ============================================================================
# International-Specific Tax Models
# ============================================================================


class QuickDeductionBracket(BaseModel):
    """
    Tax bracket using the quick deduction method (used in Japan).

    Formula: Tax = (Income * Rate) - Quick Deduction
    """

    min: float = Field(..., ge=0, description="Minimum income for this bracket")
    max: float | None = Field(None, description="Maximum income (None = unlimited)")
    rate: float = Field(..., ge=0, le=1, description="Tax rate as decimal")
    quick_deduction: float = Field(
        default=0, ge=0, description="Amount to subtract after applying rate"
    )


class IncomeTypeRate(BaseModel):
    """
    Different tax rates for specific income types (e.g., dividends, savings).

    Used in UK, Germany, and other jurisdictions with different rates by income type.
    """

    income_type: Literal[
        "dividends", "savings_interest", "capital_gains", "property", "employment"
    ] = Field(..., description="Type of income")
    brackets: list[TaxBracket] | None = Field(
        None, description="Tax brackets for this income type"
    )
    flat_rate: float | None = Field(
        None, ge=0, le=1, description="Flat rate for this income type"
    )
    allowance: float | None = Field(
        None, ge=0, description="Tax-free allowance for this income type"
    )


class StudentLoanPlan(BaseModel):
    """
    Student loan repayment configuration (UK-specific).

    PLACEHOLDER: Thresholds and rates must be verified from official sources.
    """

    plan_id: str = Field(..., description="Plan identifier (plan_1, plan_2, etc.)")
    name: str = Field(..., description="Display name")
    threshold: float = Field(..., ge=0, description="Income threshold for repayments")
    rate: float = Field(..., ge=0, le=1, description="Repayment rate as decimal")


class PersonalAllowanceTaper(BaseModel):
    """
    Personal allowance taper rules (UK-specific).

    In UK, personal allowance reduces by 1 for every 2 earned above threshold.
    """

    base_amount: float = Field(..., ge=0, description="Base personal allowance")
    taper_threshold: float = Field(
        ..., ge=0, description="Income threshold where taper begins"
    )
    taper_rate: float = Field(
        default=0.5, ge=0, le=1, description="Rate at which allowance reduces"
    )
    minimum: float = Field(default=0, ge=0, description="Minimum allowance after taper")


class FamilyQuotient(BaseModel):
    """
    Family quotient rules (France-specific).

    France divides household income by number of "parts" based on family composition.
    """

    single_adult_parts: float = Field(default=1.0, description="Parts for single adult")
    married_couple_parts: float = Field(default=2.0, description="Parts for married couple")
    first_child_parts: float = Field(default=0.5, description="Parts for first child")
    second_child_parts: float = Field(default=0.5, description="Parts for second child")
    third_plus_child_parts: float = Field(
        default=1.0, description="Parts for third+ children"
    )
    single_parent_bonus: float = Field(
        default=0.5, description="Additional parts for single parent"
    )
    cap_per_half_part: float | None = Field(
        None, ge=0, description="Maximum benefit per half-part"
    )


# ============================================================================
# Verification Models
# ============================================================================


class Reference(BaseModel):
    """Reference to an authoritative source."""

    source_name: str = Field(..., description="Name of the source")
    url: str | None = Field(None, description="URL to the source")
    retrieved_date: date | None = Field(None, description="When the source was accessed")
    notes: str | None = Field(None, description="Additional notes about the source")


class VerificationInfo(BaseModel):
    """Verification status for the entire rule set."""

    status: VerificationStatus = Field(..., description="Overall verification status")
    last_verified: date | None = Field(None, description="Date of last verification")
    verified_by: str | None = Field(None, description="Who performed verification")
    notes: str | None = Field(None, description="Verification notes")


# ============================================================================
# Main Jurisdiction Rules Model
# ============================================================================


class JurisdictionRules(BaseModel):
    """
    Complete tax rules for a jurisdiction and tax year.

    This is the main model that holds all tax rules for a single jurisdiction
    (federal, state, or local) for a specific tax year.
    """

    # Identity
    jurisdiction_id: str = Field(
        ...,
        description="Unique identifier: 'US', 'US-CA', 'US-NY-NYC'",
        # Pattern: US (federal) | US-XX (state, 2 letters) | US-XX-XXX (local, 3 letters)
        # The local part (-XXX) can only appear after the state part (-XX)
        pattern=r"^[A-Z]{2}(-[A-Z]{2}(-[A-Z]{3})?)?$",
    )
    tax_year: int = Field(
        ..., ge=2020, le=2030, description="Tax year these rules apply to"
    )

    # Metadata
    jurisdiction_type: JurisdictionType = Field(..., description="Type of jurisdiction")
    jurisdiction_name: str = Field(..., description="Display name")
    jurisdiction_abbreviation: str = Field(..., description="Short form abbreviation")
    parent_jurisdiction_id: str | None = Field(
        None, description="Parent jurisdiction for inheritance"
    )

    # Tax characteristics
    has_income_tax: bool = Field(..., description="Whether jurisdiction has income tax")
    income_tax_type: IncomeTaxType = Field(..., description="How income tax is structured")

    # Effective dates
    effective_start_date: date = Field(..., description="Start of effective period")
    effective_end_date: date = Field(..., description="End of effective period")

    # Rule components
    rate_schedule: RateSchedule = Field(..., description="Tax rate schedule")
    deductions: DeductionRules = Field(..., description="Deduction rules")

    # Payroll taxes (federal only, optional for states)
    payroll_taxes: PayrollTaxConfig | None = Field(
        default=None, description="Payroll tax configuration (federal only)"
    )

    # International extensions (optional - only for international jurisdictions)
    country_code: CountryCode | None = Field(
        default=None, description="ISO 3166-1 alpha-2 country code"
    )
    currency_code: CurrencyCode | None = Field(
        default=None, description="ISO 4217 currency code"
    )
    tax_year_format: TaxYearFormat | None = Field(
        default=None, description="How tax year is expressed"
    )

    # Social insurance (international jurisdictions)
    social_insurance: SocialInsuranceRules | None = Field(
        default=None, description="Social insurance/contribution rules"
    )

    # Country-specific rules
    personal_allowance_taper: PersonalAllowanceTaper | None = Field(
        default=None, description="UK-style personal allowance taper"
    )
    student_loan_plans: list[StudentLoanPlan] | None = Field(
        default=None, description="UK student loan repayment plans"
    )
    family_quotient: FamilyQuotient | None = Field(
        default=None, description="France-style family quotient rules"
    )
    quick_deduction_brackets: list[QuickDeductionBracket] | None = Field(
        default=None, description="Japan-style quick deduction brackets"
    )
    income_type_rates: list[IncomeTypeRate] | None = Field(
        default=None, description="Different rates for different income types"
    )

    # Surtaxes for international (e.g., Germany Soli, Japan Reconstruction Tax)
    reconstruction_tax_rate: float | None = Field(
        default=None, ge=0, le=1, description="Japan reconstruction tax rate"
    )
    solidarity_surcharge_rate: float | None = Field(
        default=None, ge=0, le=1, description="Germany solidarity surcharge rate"
    )
    church_tax_rate: float | None = Field(
        default=None, ge=0, le=1, description="Germany church tax rate"
    )

    # Verification
    verification: VerificationInfo = Field(..., description="Verification status")
    references: list[Reference] = Field(
        default_factory=list, description="Source references"
    )

    @field_validator("effective_end_date")
    @classmethod
    def validate_dates(cls, v: date, info) -> date:
        """Ensure end date is after start date."""
        start = info.data.get("effective_start_date")
        if start and v < start:
            raise ValueError("effective_end_date must be after effective_start_date")
        return v

    def get_brackets_for_status(self, filing_status: FilingStatus) -> list[TaxBracket]:
        """Get tax brackets applicable to a specific filing status."""
        return [
            b
            for b in self.rate_schedule.brackets
            if b.filing_status == filing_status or b.filing_status == "all"
        ]

    def get_standard_deduction(self, filing_status: FilingStatus) -> float:
        """Get standard deduction amount for a filing status."""
        if not self.deductions.standard_deduction.available:
            return 0.0
        for amount in self.deductions.standard_deduction.amounts:
            if amount.filing_status == filing_status:
                return amount.amount
        return 0.0
