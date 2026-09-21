"""
Pydantic models for tax calculation input.

These models define the structure of user input for tax calculations.
All monetary values should use Decimal for precision.
"""

from __future__ import annotations

from decimal import Decimal
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from tax_estimator.models.us_scenario import USScenarioFacts


class FilingStatus(str, Enum):
    """Tax filing status options."""

    SINGLE = "single"
    MFJ = "mfj"  # Married Filing Jointly
    MFS = "mfs"  # Married Filing Separately
    HOH = "hoh"  # Head of Household
    QSS = "qss"  # Qualifying Surviving Spouse


class WageIncome(BaseModel):
    """W-2 wage income from an employer."""

    employer_name: str = Field(..., description="Name of employer")
    employer_state: str = Field(
        ..., min_length=2, max_length=2, description="Two-letter state code"
    )
    gross_wages: Decimal = Field(..., ge=0, description="Box 1 wages")
    federal_withholding: Decimal = Field(
        default=Decimal(0), ge=0, description="Box 2 federal tax withheld"
    )
    state_withholding: Decimal = Field(
        default=Decimal(0), ge=0, description="Box 17 state tax withheld"
    )
    local_withholding: Decimal = Field(
        default=Decimal(0), ge=0, description="Local income tax withheld"
    )
    social_security_wages: Decimal | None = Field(
        default=None,
        ge=0,
        description="Box 3 social security wages; omitted values fall back to Box 1",
    )
    medicare_wages: Decimal | None = Field(
        default=None,
        ge=0,
        description="Box 5 Medicare wages; omitted values fall back to Box 1",
    )
    owner: Literal["taxpayer", "spouse"] = Field(
        default="taxpayer",
        description="Person whose annual Social Security wage base applies",
    )


class SelfEmploymentIncome(BaseModel):
    """Self-employment income from a business."""

    business_name: str = Field(default="", description="Name of business")
    gross_income: Decimal = Field(..., ge=0, description="Gross business income")
    expenses: Decimal = Field(default=Decimal(0), ge=0, description="Business expenses")
    owner: Literal["taxpayer", "spouse"] = Field(
        default="taxpayer",
        description="Person whose Schedule SE and Social Security wage base apply",
    )

    @property
    def net_income(self) -> Decimal:
        """Calculate net self-employment income."""
        return self.gross_income - self.expenses


class InterestDividendIncome(BaseModel):
    """Interest and dividend income."""

    taxable_interest: Decimal = Field(
        default=Decimal(0), ge=0, description="Total taxable interest"
    )
    tax_exempt_interest: Decimal = Field(
        default=Decimal(0), ge=0, description="Tax-exempt interest (municipal bonds)"
    )
    ordinary_dividends: Decimal = Field(
        default=Decimal(0), ge=0, description="Total ordinary dividends"
    )
    qualified_dividends: Decimal = Field(
        default=Decimal(0), ge=0, description="Qualified dividends (subset of ordinary)"
    )

    @field_validator("qualified_dividends")
    @classmethod
    def qualified_not_exceeding_ordinary(cls, v: Decimal, info) -> Decimal:
        """Ensure qualified dividends don't exceed ordinary dividends."""
        ordinary = info.data.get("ordinary_dividends", Decimal(0))
        if v > ordinary:
            raise ValueError("Qualified dividends cannot exceed ordinary dividends")
        return v


class CapitalGains(BaseModel):
    """Capital gains and losses."""

    short_term_gains: Decimal = Field(
        default=Decimal(0), description="Net short-term capital gains (can be negative)"
    )
    long_term_gains: Decimal = Field(
        default=Decimal(0), description="Net long-term capital gains (can be negative)"
    )
    carryover_loss: Decimal = Field(
        default=Decimal(0),
        ge=0,
        description="Legacy untyped carryover; treated as long-term loss conservatively",
    )
    short_term_carryover_loss: Decimal = Field(
        default=Decimal(0), ge=0, description="Prior-year short-term capital loss carryover"
    )
    long_term_carryover_loss: Decimal = Field(
        default=Decimal(0), ge=0, description="Prior-year long-term capital loss carryover"
    )

    @model_validator(mode="after")
    def reject_mixed_legacy_and_typed_carryovers(self) -> CapitalGains:
        """Avoid counting or inventing the character of a carryover twice."""
        if self.carryover_loss and (
            self.short_term_carryover_loss or self.long_term_carryover_loss
        ):
            raise ValueError(
                "carryover_loss cannot be combined with typed short/long-term carryovers"
            )
        return self


class RetirementIncome(BaseModel):
    """Retirement income from various sources."""

    social_security_benefits: Decimal = Field(
        default=Decimal(0), ge=0, description="Total Social Security benefits"
    )
    pension_income: Decimal = Field(default=Decimal(0), ge=0, description="Taxable pension income")
    ira_distributions: Decimal = Field(
        default=Decimal(0), ge=0, description="Traditional IRA/401k distributions"
    )
    roth_distributions: Decimal = Field(
        default=Decimal(0), ge=0, description="Qualified Roth distributions (usually tax-free)"
    )


class Adjustments(BaseModel):
    """Above-the-line adjustments to income."""

    educator_expenses: Decimal = Field(
        default=Decimal(0), ge=0, description="Educator expenses (max $300)"
    )
    hsa_contributions: Decimal = Field(default=Decimal(0), ge=0, description="HSA contributions")
    self_employed_health_insurance: Decimal = Field(
        default=Decimal(0), ge=0, description="Self-employed health insurance premiums"
    )
    self_employed_retirement: Decimal = Field(
        default=Decimal(0), ge=0, description="Self-employed retirement contributions"
    )
    student_loan_interest: Decimal = Field(
        default=Decimal(0), ge=0, description="Student loan interest (max $2,500)"
    )
    traditional_ira_contributions: Decimal = Field(
        default=Decimal(0), ge=0, description="Traditional IRA contributions"
    )
    alimony_paid: Decimal = Field(
        default=Decimal(0), ge=0, description="Alimony paid (pre-2019 divorces only)"
    )
    alimony_divorce_year: int | None = Field(default=None, description="Year of divorce decree")


class ItemizedDeductions(BaseModel):
    """Itemized deduction amounts."""

    medical_expenses: Decimal = Field(
        default=Decimal(0), ge=0, description="Total medical expenses"
    )
    state_local_taxes_paid: Decimal = Field(
        default=Decimal(0), ge=0, description="State and local income/sales taxes"
    )
    real_estate_taxes: Decimal = Field(
        default=Decimal(0), ge=0, description="Real estate property taxes"
    )
    personal_property_taxes: Decimal = Field(
        default=Decimal(0), ge=0, description="Personal property taxes"
    )
    mortgage_interest: Decimal = Field(
        default=Decimal(0), ge=0, description="Home mortgage interest"
    )
    charitable_cash: Decimal = Field(
        default=Decimal(0), ge=0, description="Cash charitable contributions"
    )
    charitable_noncash: Decimal = Field(
        default=Decimal(0), ge=0, description="Non-cash charitable contributions"
    )
    casualty_loss: Decimal = Field(
        default=Decimal(0), ge=0, description="Casualty and theft losses"
    )
    other_itemized: Decimal = Field(
        default=Decimal(0), ge=0, description="Other itemized deductions"
    )


class Dependent(BaseModel):
    """Information about a dependent."""

    name: str = Field(..., description="Dependent's name")
    relationship: str = Field(..., description="Relationship to taxpayer")
    age_at_year_end: int = Field(..., ge=0, le=120, description="Age at end of tax year")
    months_lived_with_you: int = Field(
        default=12, ge=0, le=12, description="Months lived with taxpayer"
    )
    has_ssn: bool = Field(default=True, description="Has valid SSN")
    is_student: bool = Field(default=False, description="Is full-time student")
    is_disabled: bool = Field(default=False, description="Is permanently disabled")
    qualifies_for_ctc: bool = Field(default=False, description="Qualifies for Child Tax Credit")
    qualifies_for_odc: bool = Field(
        default=False,
        description="Claimant assertion that all other-dependent-credit tests are met",
    )
    qualifies_for_eitc: bool | None = Field(
        default=None,
        description="Claimant assertion that all EITC qualifying-child tests are met",
    )

    @model_validator(mode="after")
    def reject_conflicting_dependent_credit_assertions(self) -> Dependent:
        """A dependent cannot receive both CTC and ODC for the same return."""
        if self.qualifies_for_ctc and self.qualifies_for_odc:
            raise ValueError("a dependent cannot qualify for both CTC and ODC")
        return self


class TaxpayerInfo(BaseModel):
    """Information about the taxpayer."""

    age_65_or_older: bool = Field(default=False, description="Age 65 or older")
    age_at_year_end: int | None = Field(
        default=None, ge=0, le=120, description="Age on the last day of the tax year"
    )
    is_blind: bool = Field(default=False, description="Legally blind")
    is_dependent: bool = Field(
        default=False, description="Can be claimed as dependent on another return"
    )
    has_valid_ssn_for_ctc: bool | None = Field(
        default=None,
        description="Has an employment-valid SSN issued by the 2025 return due date",
    )
    qualifies_for_enhanced_senior_deduction: bool | None = Field(
        default=None,
        description="Claimant assertion that the enhanced-senior legal/SSN tests are met",
    )

    @model_validator(mode="after")
    def reconcile_age_fields(self) -> TaxpayerInfo:
        if self.age_at_year_end is not None:
            if self.age_65_or_older and self.age_at_year_end < 65:
                raise ValueError("age_65_or_older conflicts with age_at_year_end")
            self.age_65_or_older = self.age_at_year_end >= 65
        return self


class SpouseInfo(BaseModel):
    """Information about spouse (for MFJ/MFS)."""

    age_65_or_older: bool = Field(default=False, description="Age 65 or older")
    age_at_year_end: int | None = Field(
        default=None, ge=0, le=120, description="Age on the last day of the tax year"
    )
    is_blind: bool = Field(default=False, description="Legally blind")
    has_valid_ssn_for_ctc: bool | None = Field(
        default=None,
        description="Has an employment-valid SSN issued by the 2025 return due date",
    )
    qualifies_for_enhanced_senior_deduction: bool | None = Field(
        default=None,
        description="Claimant assertion that the enhanced-senior legal/SSN tests are met",
    )

    @model_validator(mode="after")
    def reconcile_age_fields(self) -> SpouseInfo:
        if self.age_at_year_end is not None:
            if self.age_65_or_older and self.age_at_year_end < 65:
                raise ValueError("age_65_or_older conflicts with age_at_year_end")
            self.age_65_or_older = self.age_at_year_end >= 65
        return self


class TaxInput(BaseModel):
    """
    Complete tax calculation input.

    This model represents all the data needed to calculate taxes.
    """

    # Required fields
    tax_year: int = Field(..., ge=2020, le=2030, description="Tax year")
    filing_status: FilingStatus = Field(..., description="Filing status")
    residence_state: str = Field(
        ..., min_length=2, max_length=2, description="Primary residence state"
    )
    residence_zip: str | None = Field(
        default=None,
        min_length=5,
        max_length=10,
        description="Residence ZIP code (5-digit or ZIP+4)",
    )
    local_jurisdiction_id: str | None = Field(
        default=None, description="Explicit local jurisdiction for comparison scenarios"
    )
    us_scenario: USScenarioFacts = Field(default_factory=USScenarioFacts)
    lived_with_spouse_during_year: bool | None = Field(
        default=None,
        description="For MFS Social Security benefit taxation and separated-spouse rules",
    )

    # Taxpayer information
    taxpayer: TaxpayerInfo = Field(default_factory=TaxpayerInfo)
    spouse: SpouseInfo | None = Field(default=None)

    # Income sources
    wages: list[WageIncome] = Field(default_factory=list)
    self_employment: list[SelfEmploymentIncome] = Field(default_factory=list)
    interest_dividends: InterestDividendIncome = Field(default_factory=InterestDividendIncome)
    capital_gains: CapitalGains = Field(default_factory=CapitalGains)
    retirement: RetirementIncome = Field(default_factory=RetirementIncome)
    rental_income: Decimal = Field(
        default=Decimal(0), description="Net taxable rental real-estate income or loss"
    )
    other_income: Decimal = Field(default=Decimal(0), description="Other taxable income")

    # Adjustments and deductions
    adjustments: Adjustments = Field(default_factory=Adjustments)
    itemized_deductions: ItemizedDeductions | None = Field(default=None)
    force_itemize: bool = Field(
        default=False, description="Force itemized deductions even if less than standard"
    )

    # Dependents
    dependents: list[Dependent] = Field(default_factory=list)
    eitc_eligibility_asserted: bool | None = Field(
        default=None,
        description="Claimant assertion that the EITC claimant-level legal tests are met",
    )

    # Withholding and payments
    estimated_tax_payments: Decimal = Field(
        default=Decimal(0), ge=0, description="Estimated tax payments made"
    )

    @model_validator(mode="after")
    def require_mfs_social_security_living_fact(self) -> TaxInput:
        """MFS benefit taxation changes materially based on living with a spouse."""
        if (
            self.filing_status == FilingStatus.MFS
            and self.retirement.social_security_benefits > 0
            and self.lived_with_spouse_during_year is None
        ):
            raise ValueError(
                "lived_with_spouse_during_year is required for MFS filers with "
                "Social Security benefits"
            )
        return self

    @model_validator(mode="after")
    def validate_us_scenario_amounts(self) -> TaxInput:
        self.us_scenario.validate_income(
            self.total_wages(), self.capital_gains.short_term_gains,
            self.capital_gains.long_term_gains,
        )
        return self

    def total_wages(self) -> Decimal:
        """Sum of all W-2 wages."""
        return sum((w.gross_wages for w in self.wages), Decimal(0))

    def total_federal_withholding(self) -> Decimal:
        """Sum of all federal withholding."""
        return sum((w.federal_withholding for w in self.wages), Decimal(0))

    def total_medicare_wages(self) -> Decimal:
        """Sum Box 5 wages, falling back to Box 1 only when Box 5 was omitted."""
        return sum(
            (
                w.medicare_wages if w.medicare_wages is not None else w.gross_wages
                for w in self.wages
            ),
            Decimal(0),
        )

    def total_social_security_wages(self) -> Decimal:
        """Sum Box 3 wages, falling back to Box 1 only when Box 3 was omitted."""
        return sum(
            (
                w.social_security_wages if w.social_security_wages is not None else w.gross_wages
                for w in self.wages
            ),
            Decimal(0),
        )

    def total_state_withholding(self) -> Decimal:
        """Sum state tax withholding across wage statements."""
        return sum((w.state_withholding for w in self.wages), Decimal(0))

    def total_local_withholding(self) -> Decimal:
        """Sum local tax withholding across wage statements."""
        return sum((w.local_withholding for w in self.wages), Decimal(0))

    def total_self_employment_net(self) -> Decimal:
        """Sum of all net self-employment income."""
        return sum((se.net_income for se in self.self_employment), Decimal(0))
