"""
Tests enforcing that YAML is the single source of truth for federal tax data.

These tests verify:
1. The federal 2025 YAML loads without errors and is not a placeholder
2. Bracket structure matches IRS (7 brackets x 5 filing statuses = 35 total)
3. Rates match IRS Rev. Proc. 2024-40
4. base_tax values are mathematically consistent
5. No hardcoded federal brackets remain in comparison_us.py
6. Main pipeline and comparison engine produce identical federal tax
7. Spot-check known tax amounts against IRS
8. SS wage base matches 2025 ($176,100)
9. LTCG thresholds match 2025 IRS values
10. Standard deductions match 2025 IRS values
"""

from __future__ import annotations

import ast
import inspect
from decimal import Decimal
from pathlib import Path

import pytest

from tax_estimator.rules.loader import get_rules_for_jurisdiction
from tax_estimator.rules.schema import FilingStatus, JurisdictionRules


# =============================================================================
# Helpers
# =============================================================================

def _get_real_rules_dir() -> Path:
    """Get the path to the real (non-test) rules directory."""
    return Path(__file__).parent.parent / "rules"


def _load_federal_2025() -> JurisdictionRules:
    """Load the real federal 2025 rules from YAML."""
    return get_rules_for_jurisdiction("US", 2025, _get_real_rules_dir())


@pytest.fixture(scope="module")
def federal() -> JurisdictionRules:
    """Load federal 2025 rules once for the module."""
    return _load_federal_2025()


# =============================================================================
# 1. YAML loads successfully
# =============================================================================

class TestYAMLLoads:
    """YAML loads without validation errors and is not a placeholder."""

    def test_loads_without_error(self, federal: JurisdictionRules) -> None:
        assert federal is not None
        assert federal.jurisdiction_id == "US"
        assert federal.tax_year == 2025

    def test_not_placeholder(self, federal: JurisdictionRules) -> None:
        assert federal.verification.status.value != "placeholder", (
            "Federal 2025 rules are still marked as placeholder"
        )


# =============================================================================
# 2. Bracket count — 7 brackets per filing status, 35 total
# =============================================================================

class TestBracketCount:

    def test_total_bracket_count(self, federal: JurisdictionRules) -> None:
        assert len(federal.rate_schedule.brackets) == 35

    @pytest.mark.parametrize("status", ["single", "mfj", "mfs", "hoh", "qss"])
    def test_seven_brackets_per_status(
        self, federal: JurisdictionRules, status: str
    ) -> None:
        brackets = [
            b for b in federal.rate_schedule.brackets if b.filing_status == status
        ]
        assert len(brackets) == 7, f"{status} has {len(brackets)} brackets, expected 7"


# =============================================================================
# 3. Bracket rates match IRS
# =============================================================================

IRS_RATES = [0.10, 0.12, 0.22, 0.24, 0.32, 0.35, 0.37]


class TestBracketRates:

    @pytest.mark.parametrize("status", ["single", "mfj", "mfs", "hoh", "qss"])
    def test_rates_match_irs(
        self, federal: JurisdictionRules, status: str
    ) -> None:
        brackets = sorted(
            [b for b in federal.rate_schedule.brackets if b.filing_status == status],
            key=lambda b: b.income_from,
        )
        actual_rates = [b.rate for b in brackets]
        assert actual_rates == IRS_RATES, (
            f"{status} rates {actual_rates} != IRS {IRS_RATES}"
        )


# =============================================================================
# 4. base_tax values are mathematically consistent
# =============================================================================

class TestBaseTaxConsistency:
    """For each bracket, base_tax == cumulative tax from all lower brackets."""

    @pytest.mark.parametrize("status", ["single", "mfj", "mfs", "hoh", "qss"])
    def test_base_tax_values(
        self, federal: JurisdictionRules, status: str
    ) -> None:
        brackets = sorted(
            [b for b in federal.rate_schedule.brackets if b.filing_status == status],
            key=lambda b: b.income_from,
        )

        cumulative_tax = 0.0
        for i, bracket in enumerate(brackets):
            assert abs(bracket.base_tax - cumulative_tax) < 0.01, (
                f"{status} bracket {i+1} (rate={bracket.rate}): "
                f"base_tax={bracket.base_tax}, expected={cumulative_tax}"
            )
            if bracket.income_to is not None:
                bracket_width = bracket.income_to - bracket.income_from
                cumulative_tax += bracket_width * bracket.rate


# =============================================================================
# 5. No hardcoded federal brackets in comparison_us.py
# =============================================================================

class TestNoHardcodedConstants:
    """Verify comparison_us.py does not define hardcoded federal tax constants."""

    def _get_comparison_us_source(self) -> str:
        from tax_estimator.calculation import comparison_us
        return inspect.getsource(comparison_us)

    def test_no_federal_brackets_constant(self) -> None:
        source = self._get_comparison_us_source()
        assert "FEDERAL_BRACKETS" not in source, (
            "comparison_us.py still defines FEDERAL_BRACKETS — "
            "should load from YAML"
        )

    def test_no_standard_deductions_constant(self) -> None:
        source = self._get_comparison_us_source()
        assert "STANDARD_DEDUCTIONS" not in source, (
            "comparison_us.py still defines STANDARD_DEDUCTIONS — "
            "should load from YAML"
        )

    def test_no_ltcg_thresholds_constant(self) -> None:
        source = self._get_comparison_us_source()
        assert "LTCG_THRESHOLDS" not in source, (
            "comparison_us.py still defines LTCG_THRESHOLDS — "
            "should load from YAML"
        )


# =============================================================================
# 6. Main pipeline and comparison engine produce identical federal tax
# =============================================================================

class TestCrossCheckPipelineVsComparison:
    """
    The main US Tax pipeline and the Compare engine must produce
    the same federal tax for the same inputs.
    """

    def test_single_50k_federal_tax_matches(self) -> None:
        """Single filer, $50k wages — both engines should agree."""
        from tax_estimator.calculation.engine import CalculationEngine
        from tax_estimator.calculation.comparison_us import USStateComparisonCalculator
        from tax_estimator.models.tax_input import FilingStatus as FStatus, TaxInput, WageIncome
        from tax_estimator.models.income_breakdown import IncomeBreakdown

        rules_dir = _get_real_rules_dir()

        # Main pipeline
        engine = CalculationEngine(rules_dir=rules_dir)
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FStatus.SINGLE,
            residence_state="TX",  # No state tax for clean comparison
            wages=[WageIncome(
                employer_name="Test",
                employer_state="TX",
                gross_wages=Decimal("50000"),
                federal_withholding=Decimal("0"),
            )],
        )
        pipeline_result = engine.calculate(tax_input)
        assert pipeline_result.success
        pipeline_federal_tax = pipeline_result.federal.tax_before_credits

        # Comparison engine
        calculator = USStateComparisonCalculator(rules_dir=rules_dir)
        income = IncomeBreakdown(employment_wages=Decimal("50000"))
        compare_result = calculator.calculate("US-TX", income, "single", 2025)
        compare_federal_tax = compare_result.breakdown.federal_tax

        assert pipeline_federal_tax == compare_federal_tax, (
            f"Pipeline federal tax ({pipeline_federal_tax}) != "
            f"Comparison federal tax ({compare_federal_tax})"
        )

    def test_mfj_100k_federal_tax_matches(self) -> None:
        """MFJ, $100k wages — both engines should agree."""
        from tax_estimator.calculation.engine import CalculationEngine
        from tax_estimator.calculation.comparison_us import USStateComparisonCalculator
        from tax_estimator.models.tax_input import FilingStatus as FStatus, TaxInput, WageIncome, SpouseInfo
        from tax_estimator.models.income_breakdown import IncomeBreakdown

        rules_dir = _get_real_rules_dir()

        engine = CalculationEngine(rules_dir=rules_dir)
        tax_input = TaxInput(
            tax_year=2025,
            filing_status=FStatus.MFJ,
            residence_state="TX",
            spouse=SpouseInfo(),
            wages=[WageIncome(
                employer_name="Test",
                employer_state="TX",
                gross_wages=Decimal("100000"),
                federal_withholding=Decimal("0"),
            )],
        )
        pipeline_result = engine.calculate(tax_input)
        assert pipeline_result.success
        pipeline_federal_tax = pipeline_result.federal.tax_before_credits

        calculator = USStateComparisonCalculator(rules_dir=rules_dir)
        income = IncomeBreakdown(employment_wages=Decimal("100000"))
        compare_result = calculator.calculate("US-TX", income, "mfj", 2025)
        compare_federal_tax = compare_result.breakdown.federal_tax

        assert pipeline_federal_tax == compare_federal_tax, (
            f"Pipeline federal tax ({pipeline_federal_tax}) != "
            f"Comparison federal tax ({compare_federal_tax})"
        )


# =============================================================================
# 7. Spot-check known tax amounts against IRS
# =============================================================================

class TestSpotCheckTaxAmounts:
    """
    Verify computed tax matches hand-calculated IRS values.

    Hand calculations use 2025 brackets from IRS Rev. Proc. 2024-40.
    """

    @pytest.mark.parametrize(
        "filing_status,gross_wages,expected_tax,description",
        [
            # Single, $50k wages:
            #   Taxable = $50,000 - $15,000 = $35,000
            #   10% on $11,925 = $1,192.50
            #   12% on ($35,000 - $11,925 = $23,075) = $2,769.00
            #   Total = $3,961.50
            ("single", Decimal("50000"), Decimal("3961.50"), "Single $50k"),

            # Single, $100k wages:
            #   Taxable = $100,000 - $15,000 = $85,000
            #   base_tax at $48,475 = $5,578.50
            #   22% on ($85,000 - $48,475 = $36,525) = $8,035.50
            #   Total = $13,614.00
            ("single", Decimal("100000"), Decimal("13614.00"), "Single $100k"),

            # MFJ, $100k wages:
            #   Taxable = $100,000 - $30,000 = $70,000
            #   10% on $23,850 = $2,385.00
            #   12% on ($70,000 - $23,850 = $46,150) = $5,538.00
            #   Total = $7,923.00
            ("mfj", Decimal("100000"), Decimal("7923.00"), "MFJ $100k"),

            # Single, $200k wages:
            #   Taxable = $200,000 - $15,000 = $185,000
            #   base_tax at $103,350 = $17,651.00
            #   24% on ($185,000 - $103,350 = $81,650) = $19,596.00
            #   Total = $37,247.00
            ("single", Decimal("200000"), Decimal("37247.00"), "Single $200k"),

            # HOH, $75k wages:
            #   Taxable = $75,000 - $22,500 = $52,500
            #   10% on $17,000 = $1,700.00
            #   12% on ($52,500 - $17,000 = $35,500) = $4,260.00
            #   Total = $5,960.00
            ("hoh", Decimal("75000"), Decimal("5960.00"), "HOH $75k"),
        ],
    )
    def test_spot_check_ordinary_income(
        self,
        filing_status: str,
        gross_wages: Decimal,
        expected_tax: Decimal,
        description: str,
    ) -> None:
        """Verify pipeline produces correct tax for ordinary income."""
        from tax_estimator.calculation.engine import CalculationEngine
        from tax_estimator.models.tax_input import FilingStatus as FStatus, TaxInput, WageIncome, SpouseInfo

        rules_dir = _get_real_rules_dir()
        engine = CalculationEngine(rules_dir=rules_dir)

        fs_map = {
            "single": FStatus.SINGLE,
            "mfj": FStatus.MFJ,
            "mfs": FStatus.MFS,
            "hoh": FStatus.HOH,
            "qss": FStatus.QSS,
        }

        kwargs = dict(
            tax_year=2025,
            filing_status=fs_map[filing_status],
            residence_state="TX",
            wages=[WageIncome(
                employer_name="Test",
                employer_state="TX",
                gross_wages=gross_wages,
                federal_withholding=Decimal("0"),
            )],
        )
        if filing_status == "mfj":
            kwargs["spouse"] = SpouseInfo()

        result = engine.calculate(TaxInput(**kwargs))
        assert result.success, f"Pipeline failed: {result.errors}"

        actual = result.federal.tax_before_credits
        assert actual == expected_tax, (
            f"{description}: expected ${expected_tax}, got ${actual}"
        )

    def test_mixed_income_single(self) -> None:
        """
        Single, $50k wages + $100k LTCG.

        Taxable = $150,000 - $15,000 = $135,000
        Preferential (LTCG) = $100,000
        Ordinary taxable = $35,000

        Ordinary tax on $35,000:
          10% on $11,925 = $1,192.50
          12% on $23,075 = $2,769.00
          Total ordinary = $3,961.50

        LTCG on $100,000 (single, thresholds: 0%=$48,350, 15%=$533,400):
          0% room = $48,350 - $35,000 = $13,350 → $0 tax
          15% room = $533,400 - $48,350 = $485,050
          at 15%: $86,650 → $12,997.50
          Total LTCG = $12,997.50

        Total = $3,961.50 + $12,997.50 = $16,959.00
        """
        from tax_estimator.calculation.engine import CalculationEngine
        from tax_estimator.models.tax_input import (
            CapitalGains, FilingStatus as FStatus, TaxInput, WageIncome,
        )

        rules_dir = _get_real_rules_dir()
        engine = CalculationEngine(rules_dir=rules_dir)

        result = engine.calculate(TaxInput(
            tax_year=2025,
            filing_status=FStatus.SINGLE,
            residence_state="TX",
            wages=[WageIncome(
                employer_name="Test",
                employer_state="TX",
                gross_wages=Decimal("50000"),
                federal_withholding=Decimal("0"),
            )],
            capital_gains=CapitalGains(long_term_gains=Decimal("100000")),
        ))

        assert result.success
        assert result.federal.tax_before_credits == Decimal("16959.00"), (
            f"Mixed income tax: expected $16,959.00, "
            f"got ${result.federal.tax_before_credits}"
        )


# =============================================================================
# 8. SS wage base matches 2025
# =============================================================================

class TestSSWageBase:

    def test_ss_wage_base_2025(self, federal: JurisdictionRules) -> None:
        assert federal.payroll_taxes is not None
        assert federal.payroll_taxes.social_security_wage_base == 176100


# =============================================================================
# 9. LTCG thresholds match 2025 IRS values
# =============================================================================

# Source: IRS Topic 409, Rev. Proc. 2024-40
LTCG_2025 = {
    "single": (48350, 533400),
    "mfj":    (96700, 600050),
    "mfs":    (48350, 300000),
    "hoh":    (64750, 566700),
    "qss":    (96700, 600050),
}


class TestLTCGThresholds:

    @pytest.mark.parametrize("status", ["single", "mfj", "mfs", "hoh", "qss"])
    def test_ltcg_thresholds(
        self, federal: JurisdictionRules, status: str
    ) -> None:
        thresholds = {
            t.filing_status: t
            for t in federal.rate_schedule.preferential_thresholds
        }
        assert status in thresholds, f"Missing LTCG threshold for {status}"

        expected_zero, expected_fifteen = LTCG_2025[status]
        actual = thresholds[status]

        assert actual.zero_rate_limit == expected_zero, (
            f"{status} 0% limit: expected {expected_zero}, got {actual.zero_rate_limit}"
        )
        assert actual.fifteen_rate_limit == expected_fifteen, (
            f"{status} 15% limit: expected {expected_fifteen}, got {actual.fifteen_rate_limit}"
        )


# =============================================================================
# 10. Standard deductions match 2025 IRS values
# =============================================================================

STD_DED_2025 = {
    "single": 15000,
    "mfj": 30000,
    "mfs": 15000,
    "hoh": 22500,
    "qss": 30000,
}


class TestStandardDeductions:

    @pytest.mark.parametrize("status", ["single", "mfj", "mfs", "hoh", "qss"])
    def test_standard_deduction(
        self, federal: JurisdictionRules, status: str
    ) -> None:
        amounts = {
            a.filing_status.value: a.amount
            for a in federal.deductions.standard_deduction.amounts
        }
        expected = STD_DED_2025[status]
        assert amounts[status] == expected, (
            f"{status} std deduction: expected {expected}, got {amounts.get(status)}"
        )
