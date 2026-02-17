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
from typing import TYPE_CHECKING

from tax_estimator.calculation.comparison_regions import (
    RegionType,
    US_CITIES,
    US_STATES,
    NO_INCOME_TAX_STATES,
    INTEREST_DIVIDENDS_ONLY_STATES,
    get_local_jurisdiction_id,
    get_state_code_for_region,
    parse_region,
)
from tax_estimator.models.income_breakdown import (
    IncomeBreakdown,
    IncomeTypeTaxResult,
    get_income_type_display_name,
)
from tax_estimator.rules.loader import get_rules_for_jurisdiction, get_default_rules_path

if TYPE_CHECKING:
    from tax_estimator.rules.schema import JurisdictionRules

logger = logging.getLogger(__name__)

# Net Investment Income Tax (NIIT)
# Note: NIIT thresholds are NOT inflation-adjusted and have been stable since 2013.
# Not yet in the YAML schema — separate task to add.
NIIT_THRESHOLD = {
    "single": Decimal(200000),
    "mfj": Decimal(250000),
    "mfs": Decimal(125000),
    "hoh": Decimal(200000),
    "qss": Decimal(250000),  # Same as MFJ
}
NIIT_RATE = Decimal("0.038")


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

    # Local (optional)
    local_name: str | None = None
    local_tax: Decimal = field(default_factory=lambda: Decimal(0))
    local_effective_rate: Decimal = field(default_factory=lambda: Decimal(0))

    @property
    def total_tax(self) -> Decimal:
        """Total tax across all jurisdictions."""
        return self.federal_tax + self.state_tax + self.local_tax

    @property
    def total_effective_rate(self) -> Decimal:
        """Total effective rate."""
        return self.federal_effective_rate + self.state_effective_rate + self.local_effective_rate


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
        # Lazy load state/local calculators to avoid circular imports
        self._state_calculator = None
        self._local_calculator = None
        # Cache federal rules (loaded once per calculator instance)
        self._federal_rules: JurisdictionRules | None = None

    @property
    def state_calculator(self):
        """Lazy load state calculator."""
        if self._state_calculator is None:
            from tax_estimator.calculation.states.calculator import StateCalculator
            self._state_calculator = StateCalculator()
        return self._state_calculator

    @property
    def local_calculator(self):
        """Lazy load local calculator."""
        if self._local_calculator is None:
            from tax_estimator.calculation.locals.calculator import LocalCalculator
            self._local_calculator = LocalCalculator()
        return self._local_calculator

    def _get_federal_rules(self, tax_year: int = 2025) -> "JurisdictionRules":
        """Load and cache federal rules from YAML (keyed by tax_year)."""
        if self._federal_rules is None or self._federal_rules.tax_year != tax_year:
            self._federal_rules = get_rules_for_jurisdiction(
                "US", tax_year, self._rules_dir
            )
        return self._federal_rules

    def _get_brackets_for_status(
        self, filing_status: str, tax_year: int = 2025
    ) -> list[tuple[Decimal, Decimal | None, Decimal]]:
        """Get federal brackets for a filing status as (min, max, rate) tuples."""
        rules = self._get_federal_rules(tax_year)
        brackets = sorted(
            [b for b in rules.rate_schedule.brackets if b.filing_status == filing_status],
            key=lambda b: b.income_from,
        )
        if not brackets:
            raise ValueError(
                f"No federal brackets found for filing status '{filing_status}' "
                f"in tax year {tax_year}"
            )
        return [
            (
                Decimal(str(b.income_from)),
                Decimal(str(b.income_to)) if b.income_to is not None else None,
                Decimal(str(b.rate)),
            )
            for b in brackets
        ]

    def _get_standard_deduction(
        self, filing_status: str, tax_year: int = 2025
    ) -> Decimal:
        """Get standard deduction for a filing status from YAML."""
        rules = self._get_federal_rules(tax_year)
        for amt in rules.deductions.standard_deduction.amounts:
            if amt.filing_status.value == filing_status:
                return Decimal(str(amt.amount))
        # Fallback to single if status not found
        for amt in rules.deductions.standard_deduction.amounts:
            if amt.filing_status.value == "single":
                return Decimal(str(amt.amount))
        raise ValueError(f"No standard deduction found for '{filing_status}'")

    def _get_ltcg_thresholds(
        self, filing_status: str, tax_year: int = 2025
    ) -> dict[str, Decimal]:
        """Get LTCG thresholds for a filing status from YAML."""
        rules = self._get_federal_rules(tax_year)
        for t in rules.rate_schedule.preferential_thresholds:
            if t.filing_status == filing_status:
                return {
                    "zero": Decimal(str(t.zero_rate_limit)),
                    "fifteen": Decimal(str(t.fifteen_rate_limit)),
                }
        # Fallback to single
        for t in rules.rate_schedule.preferential_thresholds:
            if t.filing_status == "single":
                return {
                    "zero": Decimal(str(t.zero_rate_limit)),
                    "fifteen": Decimal(str(t.fifteen_rate_limit)),
                }
        raise ValueError(f"No LTCG thresholds found for '{filing_status}'")

    def calculate(
        self,
        region_id: str,
        income: IncomeBreakdown | Decimal,
        filing_status: str,
        tax_year: int = 2025,
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

        # Calculate federal tax
        federal_result = self._calculate_federal_tax(
            income_breakdown, filing_status, tax_year
        )

        # Calculate state tax
        state_result = self._calculate_state_tax(
            state_code, income_breakdown, filing_status, tax_year
        )

        # Calculate local tax (for cities)
        local_result = None
        if region_type == RegionType.US_CITY:
            local_jurisdiction_id = get_local_jurisdiction_id(region_id)
            if local_jurisdiction_id:
                local_result = self._calculate_local_tax(
                    local_jurisdiction_id,
                    income_breakdown,
                    filing_status,
                    tax_year,
                    state_result.get("state_tax", Decimal(0)),
                )

        # Build breakdown
        breakdown = USJurisdictionBreakdown(
            federal_taxable_income=federal_result["taxable_income"],
            federal_tax=federal_result["tax"],
            federal_effective_rate=federal_result["effective_rate"],
            federal_marginal_rate=federal_result["marginal_rate"],
            # Detailed federal breakdown
            federal_ordinary_tax=federal_result.get("ordinary_tax", Decimal(0)),
            federal_ltcg_tax=federal_result.get("preferential_tax", Decimal(0)),
            federal_niit=federal_result.get("niit", Decimal(0)),
            # LTCG bracket breakdown
            ltcg_at_zero_percent=federal_result.get("ltcg_at_zero", Decimal(0)),
            ltcg_at_fifteen_percent=federal_result.get("ltcg_at_fifteen", Decimal(0)),
            ltcg_at_twenty_percent=federal_result.get("ltcg_at_twenty", Decimal(0)),
            # NIIT details
            niit_applicable=federal_result.get("niit_applicable", False),
            niit_magi=federal_result.get("niit_magi", Decimal(0)),
            niit_threshold=federal_result.get("niit_threshold", Decimal(0)),
            niit_base=federal_result.get("niit_base", Decimal(0)),
            # State
            state_code=state_code,
            state_name=state_result["state_name"],
            state_tax=state_result["state_tax"],
            state_effective_rate=state_result["effective_rate"],
            has_state_income_tax=state_result["has_income_tax"],
            # Local
            local_name=local_result["local_name"] if local_result else None,
            local_tax=local_result["local_tax"] if local_result else Decimal(0),
            local_effective_rate=local_result["effective_rate"] if local_result else Decimal(0),
        )

        # Calculate totals
        total_tax = breakdown.total_tax
        net_income = gross_income - total_tax
        effective_rate = (total_tax / gross_income).quantize(Decimal("0.0001")) if gross_income > 0 else Decimal(0)

        # Build notes
        notes = []
        if not state_result["has_income_tax"]:
            notes.append(f"{state_result['state_name']} has no state income tax")
        if local_result and local_result["local_tax"] > 0:
            notes.append(f"Includes {local_result['local_name']} local tax")

        # Build income type results if detailed breakdown provided
        income_type_results = self._calculate_income_type_breakdown(
            income_breakdown, filing_status, tax_year, federal_result
        )

        return USComparisonResult(
            region_id=region_id,
            region_name=region_name,
            region_type=region_type,
            gross_income=gross_income,
            breakdown=breakdown,
            income_type_results=income_type_results,
            federal_tax=federal_result["tax"],
            state_tax=state_result["state_tax"],
            local_tax=local_result["local_tax"] if local_result else Decimal(0),
            total_tax=total_tax,
            net_income=net_income,
            effective_rate=effective_rate,
            notes=notes,
        )

    def _calculate_federal_tax(
        self,
        income: IncomeBreakdown,
        filing_status: str,
        tax_year: int,
    ) -> dict:
        """Calculate federal income tax."""
        gross_income = income.total

        # Standard deduction (simplified - no itemized in comparison mode)
        standard_deduction = self._get_standard_deduction(filing_status, tax_year)

        # Taxable income
        taxable_income = max(Decimal(0), gross_income - standard_deduction)

        # Split into ordinary and preferential income
        # Cap preferential at taxable_income so excess deduction spills over
        # (matches stage_06_taxable_income.py logic)
        preferential_income = min(income.preferential_income, taxable_income)
        ordinary_taxable = max(Decimal(0), taxable_income - preferential_income)

        # Calculate tax on ordinary income using brackets from YAML
        brackets = self._get_brackets_for_status(filing_status, tax_year)
        ordinary_tax, marginal_rate = self._apply_brackets(ordinary_taxable, brackets)

        # Calculate tax on preferential income (LTCG + qualified dividends)
        ltcg_result = self._calculate_preferential_tax_detailed(
            ordinary_taxable, preferential_income, filing_status
        )

        # NIIT on investment income
        niit_result = self._calculate_niit_detailed(income, filing_status)

        total_tax = ordinary_tax + ltcg_result.total_ltcg_tax + niit_result.niit_tax

        # Effective rate
        effective_rate = (total_tax / gross_income).quantize(Decimal("0.0001")) if gross_income > 0 else Decimal(0)

        return {
            "gross_income": gross_income,
            "taxable_income": taxable_income,
            "ordinary_income": ordinary_taxable,
            "ordinary_tax": ordinary_tax,
            "preferential_income": preferential_income,
            "preferential_tax": ltcg_result.total_ltcg_tax,
            "ltcg_at_zero": ltcg_result.at_zero_percent,
            "ltcg_at_fifteen": ltcg_result.at_fifteen_percent,
            "ltcg_at_twenty": ltcg_result.at_twenty_percent,
            "niit": niit_result.niit_tax,
            "niit_applicable": niit_result.applicable,
            "niit_magi": niit_result.magi,
            "niit_threshold": niit_result.threshold,
            "niit_base": niit_result.niit_base,
            "tax": total_tax,
            "effective_rate": effective_rate,
            "marginal_rate": marginal_rate,
        }

    def _apply_brackets(
        self,
        income: Decimal,
        brackets: list[tuple[Decimal, Decimal | None, Decimal]],
    ) -> tuple[Decimal, Decimal]:
        """Apply tax brackets to income."""
        if income <= 0:
            return Decimal(0), Decimal(0)

        total_tax = Decimal(0)
        remaining = income
        marginal_rate = Decimal(0)

        for bracket_min, bracket_max, rate in brackets:
            if remaining <= 0:
                break

            if bracket_max is None:
                taxable_in_bracket = remaining
            else:
                bracket_size = bracket_max - bracket_min
                taxable_in_bracket = min(remaining, bracket_size)

            tax_in_bracket = taxable_in_bracket * rate
            total_tax += tax_in_bracket
            remaining -= taxable_in_bracket
            marginal_rate = rate

        return total_tax.quantize(Decimal("0.01")), marginal_rate

    def _calculate_preferential_tax(
        self,
        ordinary_income: Decimal,
        preferential_income: Decimal,
        filing_status: str,
    ) -> Decimal:
        """Calculate tax on LTCG and qualified dividends at preferential rates."""
        result = self._calculate_preferential_tax_detailed(
            ordinary_income, preferential_income, filing_status
        )
        return result.total_ltcg_tax

    def _calculate_preferential_tax_detailed(
        self,
        ordinary_income: Decimal,
        preferential_income: Decimal,
        filing_status: str,
    ) -> FederalLTCGResult:
        """
        Calculate tax on LTCG and qualified dividends at preferential rates.

        The preferential income fills up the tax brackets from where ordinary
        income left off. Income up to the 0% threshold is taxed at 0%,
        up to the 15% threshold at 15%, and above that at 20%.

        Args:
            ordinary_income: Ordinary taxable income (after deduction)
            preferential_income: LTCG + qualified dividends
            filing_status: Filing status for threshold lookup

        Returns:
            FederalLTCGResult with detailed breakdown
        """
        if preferential_income <= 0:
            return FederalLTCGResult(
                preferential_income=Decimal(0),
                at_zero_percent=Decimal(0),
                at_fifteen_percent=Decimal(0),
                at_twenty_percent=Decimal(0),
                total_ltcg_tax=Decimal(0),
                effective_rate=Decimal(0),
            )

        thresholds = self._get_ltcg_thresholds(filing_status)

        tax = Decimal(0)
        remaining = preferential_income

        # 0% rate portion: space from ordinary income to zero threshold
        zero_rate_room = max(Decimal(0), thresholds["zero"] - ordinary_income)
        at_zero_rate = min(remaining, zero_rate_room)
        remaining -= at_zero_rate
        # tax += 0 (0% rate)

        # 15% rate portion: space from max(ordinary, zero_threshold) to fifteen threshold
        fifteen_rate_start = max(ordinary_income, thresholds["zero"])
        fifteen_rate_room = max(Decimal(0), thresholds["fifteen"] - fifteen_rate_start)
        at_fifteen_rate = min(remaining, fifteen_rate_room)
        tax += at_fifteen_rate * Decimal("0.15")
        remaining -= at_fifteen_rate

        # 20% rate portion: anything remaining
        at_twenty_rate = remaining
        tax += at_twenty_rate * Decimal("0.20")

        total_tax = tax.quantize(Decimal("0.01"))
        effective_rate = (total_tax / preferential_income).quantize(Decimal("0.0001")) if preferential_income > 0 else Decimal(0)

        return FederalLTCGResult(
            preferential_income=preferential_income,
            at_zero_percent=at_zero_rate,
            at_fifteen_percent=at_fifteen_rate,
            at_twenty_percent=at_twenty_rate,
            total_ltcg_tax=total_tax,
            effective_rate=effective_rate,
        )

    def _calculate_niit(
        self,
        income: IncomeBreakdown,
        filing_status: str,
    ) -> Decimal:
        """Calculate Net Investment Income Tax (3.8%)."""
        result = self._calculate_niit_detailed(income, filing_status)
        return result.niit_tax

    def _calculate_niit_detailed(
        self,
        income: IncomeBreakdown,
        filing_status: str,
    ) -> NIITResult:
        """
        Calculate Net Investment Income Tax (3.8%) with detailed breakdown.

        NIIT applies to the LESSER of:
        - Net Investment Income (CG + dividends + interest + rental + passive)
        - MAGI in excess of threshold

        Thresholds (NOT inflation-adjusted since 2013):
        - Single/HOH: $200,000
        - MFJ/QSS: $250,000
        - MFS: $125,000

        Args:
            income: Income breakdown
            filing_status: Filing status for threshold lookup

        Returns:
            NIITResult with detailed calculation
        """
        threshold = NIIT_THRESHOLD.get(filing_status, NIIT_THRESHOLD["single"])

        # Net Investment Income includes:
        # - Capital gains (short-term and long-term)
        # - Dividends (qualified and ordinary)
        # - Interest income (taxable)
        # - Rental income (net)
        # - Passive business income (not modeled separately)
        net_investment_income = (
            income.total_capital_gains +
            income.total_dividends +
            income.interest +
            income.rental
        )

        # MAGI (simplified - using AGI for comparison mode)
        magi = income.total
        excess_magi = max(Decimal(0), magi - threshold)

        # NIIT applies to lesser of NII or excess MAGI
        niit_base = min(net_investment_income, excess_magi)
        niit_tax = (niit_base * NIIT_RATE).quantize(Decimal("0.01"))

        return NIITResult(
            magi=magi,
            threshold=threshold,
            excess_magi=excess_magi,
            net_investment_income=net_investment_income,
            niit_base=niit_base,
            niit_tax=niit_tax,
            applicable=niit_tax > 0,
        )

    def _calculate_state_tax(
        self,
        state_code: str,
        income: IncomeBreakdown,
        filing_status: str,
        tax_year: int,
    ) -> dict:
        """Calculate state income tax."""
        region_id = f"US-{state_code}"

        # Get state info
        state_info = US_STATES.get(region_id)
        state_name = state_info.name if state_info else state_code
        has_income_tax = state_info.has_income_tax if state_info else True

        if not has_income_tax:
            return {
                "state_code": state_code,
                "state_name": state_name,
                "has_income_tax": False,
                "state_tax": Decimal(0),
                "effective_rate": Decimal(0),
            }

        # Handle interest/dividends only states (NH)
        if region_id in INTEREST_DIVIDENDS_ONLY_STATES:
            # NH only taxes interest and dividends at 3% (PLACEHOLDER)
            taxable = income.interest + income.total_dividends
            state_tax = (taxable * Decimal("0.03")).quantize(Decimal("0.01"))
            effective_rate = (state_tax / income.total).quantize(Decimal("0.0001")) if income.total > 0 else Decimal(0)
            return {
                "state_code": state_code,
                "state_name": state_name,
                "has_income_tax": True,
                "state_tax": state_tax,
                "effective_rate": effective_rate,
            }

        # Use state calculator for other states
        try:
            from tax_estimator.calculation.states.models import StateTaxInput

            # Note: State tax typically uses federal AGI as starting point
            # For comparison mode, we simplify and use gross income
            state_input = StateTaxInput(
                state_code=state_code,
                tax_year=tax_year,
                filing_status=filing_status,
                federal_agi=income.total,
                federal_taxable_income=income.total,  # Simplified
                wages=income.employment_wages,
                interest=income.interest,
                dividends=income.total_dividends,
                capital_gains=income.total_capital_gains,
            )

            result = self.state_calculator.calculate(state_input)

            return {
                "state_code": state_code,
                "state_name": result.state_name,
                "has_income_tax": result.has_income_tax,
                "state_tax": result.total_tax,
                "effective_rate": result.effective_rate,
            }

        except (ImportError, AttributeError) as e:
            # Fallback: estimate using max rate (PLACEHOLDER)
            # Log the error so users know real calculation failed
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"State calculator not available for {state_code}: {e}")

            max_rate = state_info.max_rate if state_info and state_info.max_rate else Decimal("0.05")
            # Apply a simplified estimate (actual would be lower due to brackets)
            estimated_tax = (income.total * max_rate * Decimal("0.7")).quantize(Decimal("0.01"))
            effective_rate = (estimated_tax / income.total).quantize(Decimal("0.0001")) if income.total > 0 else Decimal(0)

            return {
                "state_code": state_code,
                "state_name": state_name,
                "has_income_tax": True,
                "state_tax": estimated_tax,
                "effective_rate": effective_rate,
                "calculation_fallback": True,
            }

    def _calculate_local_tax(
        self,
        jurisdiction_id: str,
        income: IncomeBreakdown,
        filing_status: str,
        tax_year: int,
        state_tax: Decimal,
    ) -> dict:
        """Calculate local income tax."""
        try:
            result = self.local_calculator.calculate_for_jurisdiction(
                jurisdiction_id=jurisdiction_id,
                tax_year=tax_year,
                filing_status=filing_status,
                is_resident=True,
                federal_agi=income.total,
                wages=income.employment_wages,
                self_employment_income=income.self_employment,
                state_taxable_income=income.total,
                state_tax_liability=state_tax,
            )

            return {
                "local_name": result.jurisdiction_name,
                "local_tax": result.total_tax,
                "effective_rate": result.effective_rate,
            }

        except (ImportError, AttributeError) as e:
            # Fallback: no local tax - log the error
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Local calculator not available for {jurisdiction_id}: {e}")

            return {
                "local_name": "",  # Empty string instead of None for consistent structure
                "local_tax": Decimal(0),
                "effective_rate": Decimal(0),
                "calculation_fallback": True,
            }

    def _calculate_income_type_breakdown(
        self,
        income: IncomeBreakdown,
        filing_status: str,
        tax_year: int,
        federal_result: dict | None = None,
    ) -> list[IncomeTypeTaxResult]:
        """Calculate tax breakdown by income type.

        Uses actual computed federal tax data when available to provide
        accurate preferential rate calculations for LTCG and qualified dividends.
        """
        results = []

        # Compute preferential tax proration from actual federal calculation
        total_preferential_income = Decimal(0)
        preferential_tax = Decimal(0)
        if federal_result:
            total_preferential_income = federal_result.get("preferential_income", Decimal(0))
            preferential_tax = federal_result.get("preferential_tax", Decimal(0))

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

            # Determine treatment
            if income_type in ("capital_gains_long_term", "dividends_qualified"):
                treatment = "preferential"
                if federal_result and total_preferential_income > 0:
                    # Prorate the actual computed preferential tax by this
                    # income type's share of total preferential income
                    share = amount / total_preferential_income
                    estimated_tax = (preferential_tax * share).quantize(Decimal("0.01"))
                    effective_rate = (estimated_tax / amount).quantize(Decimal("0.0001")) if amount > 0 else Decimal(0)
                else:
                    estimated_tax = (amount * Decimal("0.15")).quantize(Decimal("0.01"))
                    effective_rate = Decimal("0.15")

                # Build descriptive notes from bracket data
                bracket_notes = []
                if federal_result:
                    at_zero = federal_result.get("ltcg_at_zero", Decimal(0))
                    at_fifteen = federal_result.get("ltcg_at_fifteen", Decimal(0))
                    at_twenty = federal_result.get("ltcg_at_twenty", Decimal(0))
                    if at_zero > 0:
                        bracket_notes.append("0%")
                    if at_fifteen > 0:
                        bracket_notes.append("15%")
                    if at_twenty > 0:
                        bracket_notes.append("20%")
                if bracket_notes:
                    notes = [f"Taxed at preferential rates ({'/'.join(bracket_notes)})"]
                else:
                    notes = ["Taxed at preferential 0%/15%/20% rates"]
            elif income_type == "self_employment":
                treatment = "ordinary"
                # Include SE tax estimate (~15.3% on 92.35% of SE income)
                se_tax = (amount * Decimal("0.9235") * Decimal("0.153")).quantize(Decimal("0.01"))
                # Plus income tax (estimate at 22%)
                income_tax = (amount * Decimal("0.22")).quantize(Decimal("0.01"))
                estimated_tax = se_tax + income_tax
                effective_rate = (estimated_tax / amount).quantize(Decimal("0.0001"))
                notes = ["Subject to self-employment tax + income tax"]
            else:
                treatment = "ordinary"
                # Estimate at marginal rate (simplified to 22%)
                estimated_tax = (amount * Decimal("0.22")).quantize(Decimal("0.01"))
                effective_rate = Decimal("0.22")
                notes = ["Taxed at ordinary income rates"]

            results.append(
                IncomeTypeTaxResult(
                    income_type=income_type,
                    income_type_display=display_name,
                    gross_amount=amount,
                    taxable_amount=amount,  # Simplified
                    tax_amount=estimated_tax,
                    effective_rate=effective_rate,
                    treatment=treatment,
                    notes=notes,
                )
            )

        return results


# =============================================================================
# Convenience Functions
# =============================================================================


def calculate_us_comparison(
    region_id: str,
    income: IncomeBreakdown | Decimal,
    filing_status: str = "single",
    tax_year: int = 2025,
    rules_dir: Path | None = None,
) -> USComparisonResult:
    """
    Calculate US tax for comparison.

    Convenience function for quick calculations.
    """
    calculator = USStateComparisonCalculator(rules_dir=rules_dir)
    return calculator.calculate(region_id, income, filing_status, tax_year)
