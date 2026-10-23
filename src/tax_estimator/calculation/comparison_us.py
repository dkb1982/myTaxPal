"""
US State/City comparison calculator.

Calculates federal + state + local tax for US locations in comparison mode.

Federal tax data is loaded from YAML rules (single source of truth).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any

from tax_estimator.calculation.comparison_regions import (
    US_CITIES,
    US_STATES,
    RegionType,
    get_local_jurisdiction_id,
    parse_region,
)
from tax_estimator.models.income_breakdown import (
    IncomeBreakdown,
    IncomeTypeTaxResult,
)
from tax_estimator.models.us_scenario import USScenarioFacts
from tax_estimator.rules.loader import get_default_rules_path, get_rules_for_jurisdiction

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)



# =============================================================================
# Result Models
# =============================================================================


@dataclass
class FederalLTCGResult:
    """Result of LTCG/qualified dividend tax calculation."""

    preferential_income: Decimal  # LTCG + qualified dividends
    at_zero_percent: Decimal  # Amount taxed at 0%
    at_fifteen_percent: Decimal  # Amount taxed at 15%
    at_twenty_percent: Decimal  # Amount taxed at 20%
    total_ltcg_tax: Decimal  # Total tax on preferential income
    effective_rate: Decimal  # Effective rate on preferential income


@dataclass
class NIITResult:
    """Result of NIIT calculation."""

    magi: Decimal  # Modified Adjusted Gross Income
    threshold: Decimal  # Filing status threshold
    excess_magi: Decimal  # MAGI over threshold
    net_investment_income: Decimal  # Total NII (CG + dividends + interest + rental)
    niit_base: Decimal  # Lesser of NII or excess MAGI
    niit_tax: Decimal  # 3.8% of niit_base
    applicable: bool  # Whether NIIT applies


@dataclass
class FederalTaxBreakdown:
    """Detailed federal tax breakdown."""

    # Ordinary income components
    ordinary_income: Decimal
    ordinary_income_tax: Decimal
    ordinary_marginal_rate: Decimal

    # Preferential income components (LTCG + qualified dividends)
    preferential_income: Decimal
    preferential_tax: Decimal
    preferential_at_zero: Decimal
    preferential_at_fifteen: Decimal
    preferential_at_twenty: Decimal

    # NIIT
    niit_applicable: bool
    niit_base: Decimal
    niit_tax: Decimal

    # Totals
    total_federal_tax: Decimal
    effective_rate: Decimal


@dataclass
class USJurisdictionBreakdown:
    """Tax breakdown for a US location (federal + state + local)."""

    # Federal
    federal_taxable_income: Decimal
    federal_tax: Decimal
    federal_effective_rate: Decimal
    federal_marginal_rate: Decimal

    # Federal detailed breakdown (new fields for capital gains)
    federal_ordinary_tax: Decimal = field(default_factory=lambda: Decimal(0))
    federal_ltcg_tax: Decimal = field(default_factory=lambda: Decimal(0))
    federal_niit: Decimal = field(default_factory=lambda: Decimal(0))

    employee_payroll_tax: Decimal = Decimal(0)
    employee_payroll_effective_rate: Decimal = Decimal(0)
    federal_self_employment_tax: Decimal = Decimal(0)
    federal_additional_medicare_tax: Decimal = Decimal(0)

    # LTCG breakdown details
    ltcg_at_zero_percent: Decimal = field(default_factory=lambda: Decimal(0))
    ltcg_at_fifteen_percent: Decimal = field(default_factory=lambda: Decimal(0))
    ltcg_at_twenty_percent: Decimal = field(default_factory=lambda: Decimal(0))

    # NIIT details
    niit_applicable: bool = False
    niit_magi: Decimal = field(default_factory=lambda: Decimal(0))
    niit_threshold: Decimal = field(default_factory=lambda: Decimal(0))
    niit_base: Decimal = field(default_factory=lambda: Decimal(0))

    # State
    state_code: str = ""
    state_name: str = ""
    state_tax: Decimal = field(default_factory=lambda: Decimal(0))
    state_effective_rate: Decimal = field(default_factory=lambda: Decimal(0))
    has_state_income_tax: bool = True
    state_details: dict[str, Any] = field(default_factory=dict)
    local_details: list[dict[str, Any]] = field(default_factory=list)

    # Local (optional)
    local_name: str | None = None
    local_tax: Decimal = field(default_factory=lambda: Decimal(0))
    local_effective_rate: Decimal = field(default_factory=lambda: Decimal(0))

    @property
    def total_tax(self) -> Decimal:
        """Total tax across all jurisdictions."""
        return self.federal_tax + self.state_tax + self.local_tax + self.employee_payroll_tax

    @property
    def total_effective_rate(self) -> Decimal:
        """Total effective rate."""
        return (
            self.federal_effective_rate
            + self.state_effective_rate
            + self.local_effective_rate
            + self.employee_payroll_effective_rate
        )


@dataclass
class USComparisonResult:
    """Result of US comparison calculation."""

    region_id: str
    region_name: str
    region_type: RegionType
    currency: str = "USD"

    # Income
    gross_income: Decimal = field(default_factory=lambda: Decimal(0))

    # Breakdown
    breakdown: USJurisdictionBreakdown | None = None

    # Income type results (when income breakdown provided)
    income_type_results: list[IncomeTypeTaxResult] = field(default_factory=list)

    # Totals
    federal_tax: Decimal = field(default_factory=lambda: Decimal(0))
    state_tax: Decimal = field(default_factory=lambda: Decimal(0))
    local_tax: Decimal = field(default_factory=lambda: Decimal(0))
    total_tax: Decimal = field(default_factory=lambda: Decimal(0))
    net_income: Decimal = field(default_factory=lambda: Decimal(0))
    effective_rate: Decimal = field(default_factory=lambda: Decimal(0))

    employee_payroll_tax: Decimal = Decimal(0)

    # Notes
    notes: list[str] = field(default_factory=list)


# =============================================================================
# US State Comparison Calculator
# =============================================================================


class USStateComparisonCalculator:
    """
    Calculator for US state/city tax in comparison mode.

    Calculates federal + state + local tax for a given income and filing status.
    Supports income type breakdown for more accurate comparisons.

    Federal tax data is loaded from YAML rules (single source of truth).
    """

    def __init__(self, rules_dir: Path | None = None):
        """Initialize the calculator.

        Args:
            rules_dir: Path to rules directory. Defaults to project rules/ dir.
        """
        self._rules_dir = rules_dir or get_default_rules_path()

    @property
    def rules_dir(self) -> Path:
        return self._rules_dir

    def calculate(
        self,
        region_id: str,
        income: IncomeBreakdown | Decimal,
        filing_status: str,
        tax_year: int = 2025,
        us_scenario: USScenarioFacts | None = None,
        eitc_eligibility_asserted: bool | None = None,
    ) -> USComparisonResult:
        """
        Calculate tax for a US region.

        Args:
            region_id: Region ID (e.g., 'US-CA', 'US-NY-NYC')
            income: Income breakdown or gross income
            filing_status: Filing status (single, mfj, mfs, hoh)
            tax_year: Tax year

        Returns:
            USComparisonResult with federal/state/local breakdown
        """
        # Parse region
        region_type, state_code, city_code = parse_region(region_id)

        # Convert simple income to breakdown
        if isinstance(income, Decimal):
            income_breakdown = IncomeBreakdown.from_gross_income(income)
        else:
            income_breakdown = income

        gross_income = income_breakdown.total

        # Get region info
        if region_type == RegionType.US_STATE:
            state_info = US_STATES.get(region_id)
            region_name = f"{state_info.name}, USA" if state_info else region_id
        elif region_type == RegionType.US_CITY:
            city_info = US_CITIES.get(region_id)
            region_name = city_info.display_name if city_info else region_id
            state_code = city_info.state_code if city_info else state_code
        else:
            raise ValueError(f"Invalid US region: {region_id}")

        # The standalone pipeline is the only authoritative US calculation.
        from tax_estimator.calculation.engine import CalculationEngine
        from tax_estimator.models.tax_input import (
            CapitalGains,
            InterestDividendIncome,
            SelfEmploymentIncome,
            SpouseInfo,
            TaxInput,
            TaxpayerInfo,
            WageIncome,
        )

        tax_input = TaxInput(
            tax_year=tax_year,
            filing_status=filing_status,
            taxpayer=TaxpayerInfo(age_at_year_end=40),
            us_scenario=us_scenario or USScenarioFacts(),
            eitc_eligibility_asserted=eitc_eligibility_asserted,
            spouse=SpouseInfo() if filing_status == "mfj" else None,
            residence_state=state_code,
            local_jurisdiction_id=get_local_jurisdiction_id(region_id)
            if region_type == RegionType.US_CITY
            else None,
            wages=[
                WageIncome(
                    employer_name="Comparison scenario",
                    employer_state=state_code,
                    gross_wages=income_breakdown.employment_wages,
                    social_security_wages=income_breakdown.employment_wages,
                    medicare_wages=income_breakdown.employment_wages,
                )
            ]
            if income_breakdown.employment_wages
            else [],
            self_employment=[SelfEmploymentIncome(gross_income=income_breakdown.self_employment)]
            if income_breakdown.self_employment
            else [],
            interest_dividends=InterestDividendIncome(
                taxable_interest=income_breakdown.interest,
                ordinary_dividends=income_breakdown.total_dividends,
                qualified_dividends=income_breakdown.dividends_qualified,
            ),
            capital_gains=CapitalGains(
                short_term_gains=income_breakdown.capital_gains_short_term,
                long_term_gains=income_breakdown.capital_gains_long_term,
            ),
            rental_income=income_breakdown.rental,
        )
        result = CalculationEngine(rules_dir=self._rules_dir).calculate(tax_input)
        if not result.success or result.federal is None:
            raise ValueError(f"US calculation failed: {result.errors}")
        federal = result.federal
        state = result.states[0]
        # NIIT display parameters come from the federal YAML (single source of truth).
        payroll = get_rules_for_jurisdiction("US", tax_year, self._rules_dir).payroll_taxes
        niit_threshold = Decimal(str(
            payroll.niit_threshold_mfj if filing_status in ("mfj", "qss")
            else payroll.niit_threshold_mfs if filing_status == "mfs"
            else payroll.niit_threshold_single
        ))
        niit_rate = Decimal(str(payroll.niit_rate))
        local_tax = sum((r.total_tax for r in result.locals), Decimal(0))

        # Preferential detail is supplied by the engine, not recomputed here.
        def at_rate(rate: str) -> Decimal:
            return sum(
                (
                    p.income_in_bracket
                    for p in federal.preferential_rate_breakdown
                    if p.rate == Decimal(rate)
                ),
                Decimal(0),
            )

        breakdown = USJurisdictionBreakdown(
            federal_taxable_income=federal.taxable_income,
            federal_tax=federal.total_tax,
            federal_effective_rate=federal.total_tax / gross_income if gross_income else Decimal(0),
            federal_marginal_rate=federal.marginal_rate,
            federal_ordinary_tax=federal.ordinary_tax,
            federal_ltcg_tax=federal.preferential_tax,
            federal_niit=federal.net_investment_income_tax,
            federal_self_employment_tax=federal.self_employment_tax,
            federal_additional_medicare_tax=federal.additional_medicare_tax,
            employee_payroll_tax=result.employee_payroll_tax,
            employee_payroll_effective_rate=(
                result.employee_payroll_tax / gross_income if gross_income else Decimal(0)
            ),
            ltcg_at_zero_percent=at_rate("0"),
            ltcg_at_fifteen_percent=at_rate(".15"),
            ltcg_at_twenty_percent=at_rate(".20"),
            niit_applicable=federal.net_investment_income_tax > 0,
            niit_magi=federal.adjusted_gross_income,
            niit_threshold=niit_threshold,
            niit_base=federal.net_investment_income_tax / niit_rate,
            state_code=state_code,
            state_name=state.jurisdiction_name,
            state_tax=state.total_state_tax,
            state_effective_rate=state.total_state_tax / gross_income if gross_income else Decimal(0),
            has_state_income_tax=state.has_income_tax,
            state_details=state.model_dump(),
            local_details=[r.model_dump() for r in result.locals],
            local_name=", ".join(r.jurisdiction_name for r in result.locals) or None,
            local_tax=local_tax,
            local_effective_rate=local_tax / gross_income if gross_income else Decimal(0),
        )
        total = result.total_statutory_deductions
        return USComparisonResult(
            region_id=region_id,
            region_name=region_name,
            region_type=region_type,
            gross_income=gross_income,
            breakdown=breakdown,
            income_type_results=[],
            federal_tax=federal.total_tax,
            state_tax=state.total_state_tax,
            local_tax=local_tax,
            employee_payroll_tax=result.employee_payroll_tax,
            total_tax=total,
            net_income=gross_income - total,
            effective_rate=(total / gross_income).quantize(Decimal("0.0001"))
            if gross_income
            else Decimal(0),
            notes=result.warnings
            + state.notes
            + [
                "Standard deduction; age 40 and no dependants. EITC legal eligibility is applied only when explicitly supplied. Joint wages model one earner (unvalidated state profile).",
                "Includes employee payroll, SE and Additional Medicare taxes once; excludes employer contributions.",
                "Tax by income category is not allocated: allowances and rate bands interact across categories.",
            ],
        )


# =============================================================================
# Convenience Functions
# =============================================================================


def calculate_us_comparison(
    region_id: str,
    income: IncomeBreakdown | Decimal,
    filing_status: str = "single",
    tax_year: int = 2025,
    rules_dir: Path | None = None,
    us_scenario: USScenarioFacts | None = None,
    eitc_eligibility_asserted: bool | None = None,
) -> USComparisonResult:
    """
    Calculate US tax for comparison.

    Convenience function for quick calculations.
    """
    calculator = USStateComparisonCalculator(rules_dir=rules_dir)
    return calculator.calculate(region_id, income, filing_status, tax_year,
                                us_scenario=us_scenario, eitc_eligibility_asserted=eitc_eligibility_asserted)
