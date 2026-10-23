"""
Enhanced region/country tax comparison engine.

Extends the base comparison to support:
- US states and cities in addition to international countries
- Income breakdown by type (employment, capital gains, dividends, etc.)
- Currency conversion for mixed US/international comparisons

IMPORTANT: All tax rates and exchange rates are PLACEHOLDERS for development.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from tax_estimator.calculation.comparison import (
    DEFAULT_RATE_DATE,
    get_default_exchange_rates,
)
from tax_estimator.calculation.comparison_regions import (
    NO_CGT_COUNTRIES,
    NO_TAX_COUNTRIES,
    RegionType,
    is_valid_region,
    list_all_regions,
    parse_region,
)
from tax_estimator.calculation.comparison_us import (
    USStateComparisonCalculator,
)
from tax_estimator.calculation.countries import calculate_international_tax
from tax_estimator.calculation.countries.base import UnsupportedIncomeError, get_country_name
from tax_estimator.calculation.coverage import (
    UnsupportedCoverageError,
    enabled_us_states,
    require_aligned_earnings_period,
    require_coverage,
)
from tax_estimator.calculation.profiles import comparison_profiles, profile_arguments
from tax_estimator.models.income_breakdown import (
    IncomeBreakdown,
    get_income_type_display_name,
)
from tax_estimator.models.international import (
    ExchangeRateInfo,
    InternationalTaxInput,
    get_currency_for_country,
)
from tax_estimator.models.us_scenario import USScenarioFacts

# =============================================================================
# Enhanced Response Models
# =============================================================================


class USJurisdictionBreakdownResponse(BaseModel):
    """US jurisdiction breakdown for API response."""

    # Federal basics
    federal_taxable_income: Decimal
    federal_tax: Decimal
    federal_effective_rate: Decimal
    federal_marginal_rate: Decimal

    # Federal detailed breakdown (capital gains)
    federal_ordinary_tax: Decimal = Decimal(0)
    federal_ltcg_tax: Decimal = Decimal(0)
    federal_niit: Decimal = Decimal(0)

    # LTCG bracket breakdown
    ltcg_at_zero_percent: Decimal = Decimal(0)
    ltcg_at_fifteen_percent: Decimal = Decimal(0)
    ltcg_at_twenty_percent: Decimal = Decimal(0)

    # NIIT details
    niit_applicable: bool = False
    niit_magi: Decimal = Decimal(0)
    niit_threshold: Decimal = Decimal(0)
    niit_base: Decimal = Decimal(0)

    # Payroll and federal surtaxes are separate from ordinary income tax.
    employee_payroll_tax: Decimal = Decimal(0)
    federal_self_employment_tax: Decimal = Decimal(0)
    federal_additional_medicare_tax: Decimal = Decimal(0)

    # State
    state_code: str
    state_name: str
    state_tax: Decimal
    state_effective_rate: Decimal
    has_state_income_tax: bool
    state_details: dict[str, Any] = Field(default_factory=dict)
    local_details: list[dict[str, Any]] = Field(default_factory=list)

    # Local
    local_name: str | None = None
    local_tax: Decimal = Decimal(0)
    local_effective_rate: Decimal = Decimal(0)


class InternationalBreakdownResponse(BaseModel):
    """International breakdown for API response."""

    income_tax: Decimal
    social_insurance: Decimal
    other_taxes: Decimal


class IncomeTypeTaxResponse(BaseModel):
    """Tax by income type for API response."""

    income_type: str
    income_type_display: str
    gross_amount: Decimal
    taxable_amount: Decimal
    tax_amount: Decimal
    effective_rate: Decimal
    treatment: str
    notes: list[str] = Field(default_factory=list)


class EnhancedRegionResult(BaseModel):
    """Enhanced result for a single region."""

    # Identification
    region_id: str
    region_name: str
    region_type: str  # "us_state", "us_city", "international"
    currency_code: str

    # Totals in local currency
    gross_income_local: Decimal
    total_tax_local: Decimal
    net_income_local: Decimal

    # Totals in base currency (for comparison)
    gross_income_base: Decimal
    total_tax_base: Decimal
    net_income_base: Decimal

    # Rate
    effective_rate: Decimal

    # Jurisdiction breakdown (one populated based on type)
    us_breakdown: USJurisdictionBreakdownResponse | None = None
    international_breakdown: InternationalBreakdownResponse | None = None

    # Income type breakdown (when detailed income provided)
    income_type_results: list[IncomeTypeTaxResponse] = Field(default_factory=list)

    # Notes
    notes: list[str] = Field(default_factory=list)


class SkippedRegion(BaseModel):
    """A selected country that could not be modelled for the supplied income."""

    region_id: str
    region_name: str
    reason: str


class EnhancedComparisonResult(BaseModel):
    """Enhanced comparison result with US and international support."""

    # Input echo
    base_currency: str
    tax_year: int
    filing_status: str | None = None

    # Income summary
    total_gross_income: Decimal
    income_breakdown: dict[str, Decimal] | None = None

    # Exchange rates
    exchange_rates: ExchangeRateInfo

    # Results
    regions: list[EnhancedRegionResult] = Field(default_factory=list)

    # Countries left out because an income type or profile is not modelled
    skipped_regions: list[SkippedRegion] = Field(default_factory=list)

    # Rankings
    lowest_tax_region: str | None = None
    highest_net_income_region: str | None = None

    # Disclaimers
    disclaimers: list[str] = Field(
        default_factory=lambda: [
            "This comparison is for informational purposes only.",
            "Each place is estimated for a default profile checked against official 2025 sources; this is not a complete tax return, and personal circumstances outside that profile are not modelled.",
            "Default FX is the published IRS 2025 annual average, not a live or transaction-date rate.",
            "Independent full-year domestic scenarios with equal converted gross income; continuing home-country tax, treaties, immigration and cost of living are not modelled.",
            "Consult a tax professional before making relocation decisions.",
        ]
    )


# =============================================================================
# Enhanced Comparison Engine
# =============================================================================


class EnhancedComparisonEngine:
    """
    Enhanced comparison engine supporting US states/cities and income breakdown.

    Supports:
    - US states (US-XX format)
    - US cities (US-XX-YYY format)
    - International countries (XX format)
    - Income type breakdown
    - Currency conversion for mixed comparisons

    IMPORTANT: All calculations use PLACEHOLDER rates.
    """

    def __init__(
        self,
        exchange_rates: dict[str, Decimal] | None = None,
        rate_date: str | None = None,
        rate_source: str | None = None,
        rules_dir: Path | None = None,
    ):
        """Initialize the enhanced comparison engine."""
        from tax_estimator.calculation.comparison import (
            DEFAULT_RATE_SOURCE,
            validate_exchange_rates,
        )

        self._rates = (
            validate_exchange_rates(exchange_rates)
            if exchange_rates is not None
            else get_default_exchange_rates()
        )
        self._rate_date = rate_date or DEFAULT_RATE_DATE
        self._rate_source = rate_source or (
            DEFAULT_RATE_SOURCE if exchange_rates is None else "User-supplied rates"
        )
        self._us_calculator = USStateComparisonCalculator(rules_dir=rules_dir)
        self._rules_dir = self._us_calculator.rules_dir

    def convert_currency(
        self,
        amount: Decimal,
        from_currency: str,
        to_currency: str,
    ) -> Decimal:
        """Convert amount between currencies."""
        if from_currency not in self._rates or to_currency not in self._rates:
            raise ValueError(f"Missing exchange rate for {from_currency} or {to_currency}")
        if from_currency == to_currency:
            return amount

        from_rate = self._rates.get(from_currency, Decimal("1.0"))
        to_rate = self._rates.get(to_currency, Decimal("1.0"))

        if from_rate <= 0 or to_rate <= 0:
            invalid_currencies = []
            if from_rate <= 0:
                invalid_currencies.append(f"{from_currency} (rate: {from_rate})")
            if to_rate <= 0:
                invalid_currencies.append(f"{to_currency} (rate: {to_rate})")
            raise ValueError(f"Invalid exchange rate for: {', '.join(invalid_currencies)}")

        amount_usd = amount / from_rate
        amount_to = amount_usd * to_rate

        return amount_to.quantize(Decimal("0.01"))

    def compare(
        self,
        regions: list[str],
        income: IncomeBreakdown | Decimal,
        base_currency: str = "USD",
        filing_status: str = "single",
        tax_year: int = 2025,
        country_profiles: dict[str, Any] | None = None,
        us_scenario: USScenarioFacts | None = None,
        eitc_eligibility_asserted: bool | None = None,
    ) -> EnhancedComparisonResult:
        """
        Compare tax across multiple regions.

        Args:
            regions: List of region IDs (e.g., ["US-CA", "US-TX", "SG", "AE"])
            income: Income breakdown or gross income
            base_currency: Currency for comparison (default USD)
            filing_status: US filing status (default single)
            tax_year: Tax year

        Returns:
            EnhancedComparisonResult with all comparisons
        """
        if tax_year not in {2025, 2026}:
            raise ValueError("Only tax years 2025 and 2026 are supported for comparison")

        # Convert simple income to breakdown
        if isinstance(income, Decimal):
            income_breakdown = IncomeBreakdown.from_gross_income(income)
        else:
            income_breakdown = income

        if tax_year == 2026:
            supported_regions = {
                f"US-{code}"
                for code in enabled_us_states(2026, rules_root=self._rules_dir)
            }
            unsupported = sorted(set(regions) - supported_regions)
            if unsupported:
                raise UnsupportedComparisonCoverageError(
                    "2026 comparison is not validated for: " + ", ".join(unsupported)
                )
            if base_currency != "USD":
                raise UnsupportedComparisonCoverageError(
                    "2026 US comparison requires USD; no 2026 annual-average FX rate is available"
                )
            if filing_status != "single":
                raise UnsupportedComparisonCoverageError(
                    "2026 US comparison currently supports single filers only"
                )
            if country_profiles:
                raise UnsupportedComparisonCoverageError(
                    "2026 US comparison does not support country profiles"
                )
            if us_scenario is not None and us_scenario.model_dump(exclude_defaults=True):
                raise UnsupportedComparisonCoverageError(
                    "2026 US comparison does not support state or city scenario adjustments"
                )
            active_income = frozenset(
                name for name, amount in income_breakdown.to_dict().items() if amount
            )
            try:
                coverage = tuple(
                    require_coverage(
                        region_id, 2026, rules_root=self._rules_dir,
                        income_categories=active_income
                    )
                    for region_id in regions
                )
                require_aligned_earnings_period(coverage)
            except UnsupportedCoverageError as exc:
                raise UnsupportedComparisonCoverageError(str(exc)) from exc

        gross_income = income_breakdown.total
        if us_scenario is not None:
            us_scenario.validate_income(income_breakdown.employment_wages,
                                       income_breakdown.capital_gains_short_term,
                                       income_breakdown.capital_gains_long_term)

        # Validate regions
        invalid = [r for r in regions if not is_valid_region(r)]
        if invalid:
            raise ValueError(f"Invalid regions: {invalid}")
        country_profiles = comparison_profiles(country_profiles, regions)
        if not regions or len(regions) != len(set(regions)):
            raise ValueError("Supply at least one unique region")
        if base_currency not in self._rates:
            raise ValueError(f"Missing exchange rate for {base_currency}")

        # Calculate for each region
        results: list[EnhancedRegionResult] = []
        skipped: list[SkippedRegion] = []
        for region_id in regions:
            try:
                result = self._calculate_for_region(
                    region_id=region_id,
                    income=income_breakdown,
                    base_currency=base_currency,
                    filing_status=filing_status,
                    tax_year=tax_year,
                    country_profiles=country_profiles or {},
                    us_scenario=us_scenario,
                    eitc_eligibility_asserted=eitc_eligibility_asserted,
                )
            except UnsupportedIncomeError as exc:
                # A country that cannot model this income (e.g. German
                # self-employment) is listed as skipped instead of failing the
                # whole comparison. Anything else, including US required-fact,
                # coverage and configuration errors, still fails closed.
                skipped.append(SkippedRegion(
                    region_id=region_id,
                    region_name=get_country_name(region_id),
                    reason=str(exc),
                ))
                continue
            results.append(result)
        if not results:
            raise ValueError("; ".join(item.reason for item in skipped))

        # Find best options
        lowest_tax_region = None
        highest_net_region = None
        lowest_tax = None
        highest_net = None

        for result in results:
            if lowest_tax is None or result.total_tax_base < lowest_tax:
                lowest_tax = result.total_tax_base
                lowest_tax_region = result.region_id
            if highest_net is None or result.net_income_base > highest_net:
                highest_net = result.net_income_base
                highest_net_region = result.region_id

        # Create exchange rate info
        exchange_info = ExchangeRateInfo(
            base_currency=base_currency,
            rates={"USD": Decimal(1)} if tax_year == 2026 else dict(self._rates),
            rate_date="not applicable" if tax_year == 2026 else self._rate_date,
            source="No currency conversion (USD only)" if tax_year == 2026 else self._rate_source,
        )

        # Build income breakdown dict if detailed
        income_dict = None
        if not isinstance(income, Decimal):
            income_dict = income_breakdown.to_dict()

        comparison = EnhancedComparisonResult(
            base_currency=base_currency,
            tax_year=tax_year,
            filing_status=filing_status if any(r.startswith("US-") for r in regions) else None,
            total_gross_income=gross_income,
            income_breakdown=income_dict,
            exchange_rates=exchange_info,
            regions=results,
            skipped_regions=skipped,
            lowest_tax_region=lowest_tax_region,
            highest_net_income_region=highest_net_region,
        )
        if tax_year == 2026:
            comparison.disclaimers = [
                "2026 US estimate for the listed supported states only; not a complete tax return.",
                "Single, age 40, no dependants, full-year same-state employee; "
                "standard deduction and direct securities gains.",
                "Qualified tips and overtime, car-loan interest, charity, itemization, "
                "and other special deductions are not modelled.",
                "EITC claimant eligibility is applied only when explicitly asserted; "
                "filed-return tables may differ from the continuous estimate.",
                "USD only; no 2025 exchange rate is applied to this 2026 comparison.",
            ]
        return comparison

    def _calculate_for_region(
        self,
        region_id: str,
        income: IncomeBreakdown,
        base_currency: str,
        filing_status: str,
        tax_year: int,
        country_profiles: dict[str, Any],
        us_scenario: USScenarioFacts | None = None,
        eitc_eligibility_asserted: bool | None = None,
    ) -> EnhancedRegionResult:
        """Calculate tax for a single region."""
        region_type, code, city_code = parse_region(region_id)

        if region_type in (RegionType.US_STATE, RegionType.US_CITY):
            return self._calculate_us_region(
                region_id=region_id,
                region_type=region_type,
                income=income,
                base_currency=base_currency,
                filing_status=filing_status,
                tax_year=tax_year,
                us_scenario=us_scenario,
                eitc_eligibility_asserted=eitc_eligibility_asserted,
            )
        else:
            return self._calculate_international_region(
                country_code=region_id,
                income=income,
                base_currency=base_currency,
                tax_year=tax_year,
                country_profiles=country_profiles,
            )

    def _calculate_us_region(
        self,
        region_id: str,
        region_type: RegionType,
        income: IncomeBreakdown,
        base_currency: str,
        filing_status: str,
        tax_year: int,
        us_scenario: USScenarioFacts | None = None,
        eitc_eligibility_asserted: bool | None = None,
    ) -> EnhancedRegionResult:
        """Calculate tax for a US state or city."""
        # US is always in USD
        currency = "USD"

        # Convert income to USD if needed
        if base_currency != "USD":
            usd_income = IncomeBreakdown(
                employment_wages=self.convert_currency(
                    income.employment_wages, base_currency, "USD"
                ),
                capital_gains_short_term=self.convert_currency(
                    income.capital_gains_short_term, base_currency, "USD"
                ),
                capital_gains_long_term=self.convert_currency(
                    income.capital_gains_long_term, base_currency, "USD"
                ),
                dividends_qualified=self.convert_currency(
                    income.dividends_qualified, base_currency, "USD"
                ),
                dividends_ordinary=self.convert_currency(
                    income.dividends_ordinary, base_currency, "USD"
                ),
                interest=self.convert_currency(income.interest, base_currency, "USD"),
                self_employment=self.convert_currency(income.self_employment, base_currency, "USD"),
                rental=self.convert_currency(income.rental, base_currency, "USD"),
            )
        else:
            usd_income = income

        # Category facts use the same request currency and conversion as income.
        usd_scenario = USScenarioFacts(**{
            key: self.convert_currency(value, base_currency, "USD") if base_currency != "USD" else value
            for key, value in (us_scenario or USScenarioFacts()).model_dump(exclude_none=True).items()
        })
        # Calculate using US calculator
        us_result = self._us_calculator.calculate(
            region_id=region_id,
            income=usd_income,
            filing_status=filing_status,
            tax_year=tax_year,
            us_scenario=usd_scenario,
            eitc_eligibility_asserted=eitc_eligibility_asserted,
        )

        # Build US breakdown response
        us_breakdown = None
        if us_result.breakdown:
            us_breakdown = USJurisdictionBreakdownResponse(
                # Federal basics
                federal_taxable_income=us_result.breakdown.federal_taxable_income,
                federal_tax=us_result.breakdown.federal_tax,
                federal_effective_rate=us_result.breakdown.federal_effective_rate,
                federal_marginal_rate=us_result.breakdown.federal_marginal_rate,
                # Federal detailed breakdown (capital gains)
                federal_ordinary_tax=us_result.breakdown.federal_ordinary_tax,
                federal_ltcg_tax=us_result.breakdown.federal_ltcg_tax,
                federal_niit=us_result.breakdown.federal_niit,
                # LTCG bracket breakdown
                ltcg_at_zero_percent=us_result.breakdown.ltcg_at_zero_percent,
                ltcg_at_fifteen_percent=us_result.breakdown.ltcg_at_fifteen_percent,
                ltcg_at_twenty_percent=us_result.breakdown.ltcg_at_twenty_percent,
                # NIIT details
                niit_applicable=us_result.breakdown.niit_applicable,
                niit_magi=us_result.breakdown.niit_magi,
                niit_threshold=us_result.breakdown.niit_threshold,
                niit_base=us_result.breakdown.niit_base,
                employee_payroll_tax=us_result.breakdown.employee_payroll_tax,
                federal_self_employment_tax=us_result.breakdown.federal_self_employment_tax,
                federal_additional_medicare_tax=us_result.breakdown.federal_additional_medicare_tax,
                # State
                state_code=us_result.breakdown.state_code,
                state_name=us_result.breakdown.state_name,
                state_tax=us_result.breakdown.state_tax,
                state_details=us_result.breakdown.state_details,
                local_details=us_result.breakdown.local_details,
                state_effective_rate=us_result.breakdown.state_effective_rate,
                has_state_income_tax=us_result.breakdown.has_state_income_tax,
                # Local
                local_name=us_result.breakdown.local_name,
                local_tax=us_result.breakdown.local_tax,
                local_effective_rate=us_result.breakdown.local_effective_rate,
            )

        # Convert results back to base currency
        gross_income_base = income.total
        total_tax_base = self.convert_currency(us_result.total_tax, "USD", base_currency)
        net_income_base = gross_income_base - total_tax_base

        # Build income type responses
        income_type_responses = [
            IncomeTypeTaxResponse(
                income_type=itr.income_type,
                income_type_display=itr.income_type_display,
                gross_amount=itr.gross_amount,
                taxable_amount=itr.taxable_amount,
                tax_amount=itr.tax_amount,
                effective_rate=itr.effective_rate,
                treatment=itr.treatment,
                notes=itr.notes,
            )
            for itr in us_result.income_type_results
        ]

        return EnhancedRegionResult(
            region_id=region_id,
            region_name=us_result.region_name,
            region_type=region_type.value,
            currency_code=currency,
            gross_income_local=us_result.gross_income,
            total_tax_local=us_result.total_tax,
            net_income_local=us_result.net_income,
            gross_income_base=gross_income_base,
            total_tax_base=total_tax_base,
            net_income_base=net_income_base,
            effective_rate=us_result.effective_rate,
            us_breakdown=us_breakdown,
            income_type_results=income_type_responses,
            notes=us_result.notes,
        )

    def _calculate_international_region(
        self,
        country_code: str,
        income: IncomeBreakdown,
        base_currency: str,
        tax_year: int,
        country_profiles: dict[str, Any],
    ) -> EnhancedRegionResult:
        """Calculate tax for an international country."""
        local_currency = get_currency_for_country(country_code)

        # Convert income to local currency
        if base_currency != local_currency:
            local_income = IncomeBreakdown(
                employment_wages=self.convert_currency(
                    income.employment_wages, base_currency, local_currency
                ),
                capital_gains_short_term=self.convert_currency(
                    income.capital_gains_short_term, base_currency, local_currency
                ),
                capital_gains_long_term=self.convert_currency(
                    income.capital_gains_long_term, base_currency, local_currency
                ),
                dividends_qualified=self.convert_currency(
                    income.dividends_qualified, base_currency, local_currency
                ),
                dividends_ordinary=self.convert_currency(
                    income.dividends_ordinary, base_currency, local_currency
                ),
                interest=self.convert_currency(income.interest, base_currency, local_currency),
                self_employment=self.convert_currency(
                    income.self_employment, base_currency, local_currency
                ),
                rental=self.convert_currency(income.rental, base_currency, local_currency),
            )
        else:
            local_income = income

        # Calculate using international calculator with income type breakdown
        tax_input = InternationalTaxInput(
            country_code=country_code,
            tax_year=tax_year,
            currency_code=local_currency,
            gross_income=local_income.total,
            income_breakdown=local_income,
            **profile_arguments(country_code, country_profiles),
        )

        result = calculate_international_tax(tax_input)

        # A country calculator is the sole authority for its liability.  The
        # old per-category helper invented 25% rates and overwrote that result.
        # Category tax cannot in general be allocated without changing band
        # interactions, so leave the optional allocation empty rather than lie.
        income_type_results: list[IncomeTypeTaxResponse] = []
        total_tax_local = result.total_tax

        net_income_local = local_income.total - total_tax_local
        effective_rate = (
            (total_tax_local / local_income.total).quantize(Decimal("0.0001"))
            if local_income.total > 0
            else Decimal(0)
        )

        # Convert back to base currency
        total_tax_base = self.convert_currency(total_tax_local, local_currency, base_currency)
        net_income_base = income.total - total_tax_base

        # Preserve the calculator's reconciled components unchanged.
        intl_breakdown = InternationalBreakdownResponse(
            income_tax=result.income_tax,
            social_insurance=result.social_insurance,
            other_taxes=result.other_taxes,
        )

        return EnhancedRegionResult(
            region_id=country_code,
            region_name=get_country_name(country_code),
            region_type=RegionType.INTERNATIONAL.value,
            currency_code=local_currency,
            gross_income_local=local_income.total,
            total_tax_local=total_tax_local,
            net_income_local=net_income_local,
            gross_income_base=income.total,
            total_tax_base=total_tax_base,
            net_income_base=net_income_base,
            effective_rate=effective_rate,
            international_breakdown=intl_breakdown,
            income_type_results=income_type_results,
            notes=result.calculation_notes
            + result.warnings
            + [
                "No category-specific tax allocation: allowances and rate bands interact.",
                "Profile relief amounts, when supplied, are in destination currency.",
            ],
        )

    def _calculate_international_income_types(
        self,
        country_code: str,
        income: IncomeBreakdown,
        tax_year: int,
    ) -> list[IncomeTypeTaxResponse]:
        """
        Calculate income type breakdown for international countries.

        Applies country-specific rules:
        - Singapore/HK/UAE: No capital gains tax
        - UAE: No income tax at all
        - UK: CGT with annual exempt amount
        - etc.
        """
        results = []

        # Country-specific treatment
        no_cgt = country_code in NO_CGT_COUNTRIES
        no_tax = country_code in NO_TAX_COUNTRIES

        income_types = [
            ("employment_wages", income.employment_wages),
            ("capital_gains_short_term", income.capital_gains_short_term),
            ("capital_gains_long_term", income.capital_gains_long_term),
            ("dividends_qualified", income.dividends_qualified),
            ("dividends_ordinary", income.dividends_ordinary),
            ("interest", income.interest),
            ("self_employment", income.self_employment),
            ("rental", income.rental),
        ]

        for income_type, amount in income_types:
            if amount <= 0:
                continue

            display_name = get_income_type_display_name(income_type)

            if no_tax:
                # UAE - no personal income tax
                results.append(
                    IncomeTypeTaxResponse(
                        income_type=income_type,
                        income_type_display=display_name,
                        gross_amount=amount,
                        taxable_amount=Decimal(0),
                        tax_amount=Decimal(0),
                        effective_rate=Decimal(0),
                        treatment="exempt",
                        notes=["No personal income tax in UAE"],
                    )
                )
            elif no_cgt and income_type in ("capital_gains_short_term", "capital_gains_long_term"):
                # No CGT in SG/HK
                results.append(
                    IncomeTypeTaxResponse(
                        income_type=income_type,
                        income_type_display=display_name,
                        gross_amount=amount,
                        taxable_amount=Decimal(0),
                        tax_amount=Decimal(0),
                        effective_rate=Decimal(0),
                        treatment="exempt",
                        notes=[f"No capital gains tax in {get_country_name(country_code)}"],
                    )
                )
            elif (
                no_cgt
                and country_code in ("SG", "HK")
                and income_type in ("dividends_qualified", "dividends_ordinary")
            ):
                # No dividend tax in SG/HK
                results.append(
                    IncomeTypeTaxResponse(
                        income_type=income_type,
                        income_type_display=display_name,
                        gross_amount=amount,
                        taxable_amount=Decimal(0),
                        tax_amount=Decimal(0),
                        effective_rate=Decimal(0),
                        treatment="exempt",
                        notes=[f"Dividends not taxed in {get_country_name(country_code)}"],
                    )
                )
            elif country_code == "GB" and income_type in (
                "capital_gains_short_term",
                "capital_gains_long_term",
            ):
                # UK CGT with annual exempt amount (PLACEHOLDER: 6000 GBP)
                exempt_amount = Decimal(6000)
                taxable = max(Decimal(0), amount - exempt_amount)
                # PLACEHOLDER: 20% CGT rate for higher rate taxpayer
                tax = (taxable * Decimal("0.20")).quantize(Decimal("0.01"))
                effective = (tax / amount).quantize(Decimal("0.0001")) if amount > 0 else Decimal(0)
                results.append(
                    IncomeTypeTaxResponse(
                        income_type=income_type,
                        income_type_display=display_name,
                        gross_amount=amount,
                        taxable_amount=taxable,
                        tax_amount=tax,
                        effective_rate=effective,
                        treatment="cgt_with_allowance",
                        notes=[
                            "Annual exempt amount of 6,000 GBP applied",
                            "CGT at 20% (PLACEHOLDER)",
                        ],
                    )
                )
            else:
                # Default: taxed at ordinary rates (PLACEHOLDER: 25% estimate)
                estimated_rate = Decimal("0.25")
                tax = (amount * estimated_rate).quantize(Decimal("0.01"))
                results.append(
                    IncomeTypeTaxResponse(
                        income_type=income_type,
                        income_type_display=display_name,
                        gross_amount=amount,
                        taxable_amount=amount,
                        tax_amount=tax,
                        effective_rate=estimated_rate,
                        treatment="ordinary",
                        notes=["Taxed at ordinary income rates (PLACEHOLDER)"],
                    )
                )

        return results


# =============================================================================
# Convenience Functions
# =============================================================================


def compare_regions_enhanced(
    regions: list[str],
    income: IncomeBreakdown | Decimal,
    base_currency: str = "USD",
    filing_status: str = "single",
    tax_year: int = 2025,
    country_profiles: dict[str, Any] | None = None,
    us_scenario: USScenarioFacts | None = None,
    eitc_eligibility_asserted: bool | None = None,
    rules_dir: Path | None = None,
) -> EnhancedComparisonResult:
    """
    Compare tax across multiple regions with enhanced support.

    Convenience function for the enhanced comparison engine.

    Args:
        regions: List of region IDs (e.g., ["US-CA", "US-TX", "SG", "AE"])
        income: Income breakdown or gross income
        base_currency: Currency for comparison
        filing_status: US filing status
        tax_year: Tax year

    Returns:
        EnhancedComparisonResult with all comparisons
    """
    engine = EnhancedComparisonEngine(rules_dir=rules_dir)
    return engine.compare(
        regions=regions,
        income=income,
        base_currency=base_currency,
        filing_status=filing_status,
        tax_year=tax_year,
        country_profiles=country_profiles,
        us_scenario=us_scenario,
        eitc_eligibility_asserted=eitc_eligibility_asserted,
    )


class UnsupportedComparisonCoverageError(ValueError):
    """A requested year/profile/jurisdiction is outside validated coverage."""


def get_all_comparison_regions(
    tax_year: int = 2025, rules_dir: Path | None = None
) -> dict[str, list[dict[str, Any]]]:
    """Get all available comparison regions."""
    regions = list_all_regions()
    if tax_year == 2025:
        return regions
    if tax_year == 2026:
        supported_regions = {
            f"US-{code}"
            for code in enabled_us_states(2026, rules_root=rules_dir)
        }
        return {
            "us_states": [
                state for state in regions["us_states"]
                if state["region_id"] in supported_regions
            ],
            "us_cities": [],
            "international": [],
        }
    raise UnsupportedComparisonCoverageError(
        f"No comparison regions are validated for {tax_year}"
    )
